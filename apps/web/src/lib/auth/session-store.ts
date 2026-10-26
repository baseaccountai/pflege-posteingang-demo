// Server-side session store (F01-AC3): the browser only gets a random session id in
// the cookie; the tokens live in bff.sessions, encrypted with AES-256-GCM. The table
// stores only sha256(session id), so a stolen table row cannot be used as a cookie.
import { createCipheriv, createDecipheriv, createHash, randomBytes } from "node:crypto";
import type postgres from "postgres";

export type TokenSet = { access: string; refresh: string | null; id: string | null };

const VERSION = 1; // first byte of tokens_enc, allows a later key/format change
const IV_BYTES = 12;
const TAG_BYTES = 16;

/** 256 random bits, base64url: the value of the __Host-pp_sid cookie. */
export function newSessionId(): string {
  return randomBytes(32).toString("base64url");
}

export function hashSessionId(sid: string): Buffer {
  return createHash("sha256").update(sid).digest();
}

/** SESSION_ENC_KEY: 32 random bytes, base64 (e.g. `openssl rand -base64 32`). */
export function parseEncKey(value: string | undefined): Buffer {
  const key = Buffer.from(value ?? "", "base64");
  if (key.length !== 32) throw new Error("SESSION_ENC_KEY must be 32 bytes, base64-encoded");
  return key;
}

/**
 * Layout: version (1) | iv (12) | ciphertext | tag (16).
 * The row's id_hash is authenticated data: the ciphertext only opens in its own row.
 */
export function sealTokens(tokens: TokenSet, key: Buffer, idHash: Buffer): Buffer {
  const iv = randomBytes(IV_BYTES);
  const cipher = createCipheriv("aes-256-gcm", key, iv);
  cipher.setAAD(idHash);
  const body = Buffer.concat([cipher.update(JSON.stringify(tokens), "utf8"), cipher.final()]);
  return Buffer.concat([Buffer.from([VERSION]), iv, body, cipher.getAuthTag()]);
}

/** Throws if the data was changed, belongs to another row or another key. */
export function openTokens(sealed: Buffer, key: Buffer, idHash: Buffer): TokenSet {
  if (sealed[0] !== VERSION) throw new Error("unknown token format");
  const iv = sealed.subarray(1, 1 + IV_BYTES);
  const tag = sealed.subarray(sealed.length - TAG_BYTES);
  const decipher = createDecipheriv("aes-256-gcm", key, iv);
  decipher.setAAD(idHash);
  decipher.setAuthTag(tag);
  const body = sealed.subarray(1 + IV_BYTES, sealed.length - TAG_BYTES);
  return JSON.parse(Buffer.concat([decipher.update(body), decipher.final()]).toString("utf8"));
}

// --- bff.sessions (role bff_session, see supabase/migrations/*_f01_auth.sql) ------------

export type Session = {
  sub: string;
  appRole: string;
  displayName: string;
  tokens: TokenSet;
  accessExpiresAt: Date;
  expiresAt: Date;
};

export type NewSession = Omit<Session, "expiresAt">;

/** What the IdP returns on refresh; a missing refresh/id token keeps the old one. */
export type Refreshed = {
  tokens: { access: string; refresh?: string | null; id?: string | null };
  accessExpiresAt: Date;
};

type Row = {
  id_hash: Buffer;
  sub: string;
  app_role: string;
  display_name: string;
  tokens_enc: Buffer;
  access_expires_at: Date;
  expires_at: Date;
  due: boolean;
};

// Absolute session end (F01-AC21); a token refresh does not extend it.
const SESSION_LIFETIME = "8 hours";
// Refresh shortly before the access token expires, so the API never sees an expired one.
const REFRESH_MARGIN = "60 seconds";

export class SessionStore {
  constructor(
    private readonly sql: postgres.Sql,
    private readonly key: Buffer,
  ) {}

  /** Creates the row and returns the session id for the cookie (never stored). */
  async create(session: NewSession): Promise<string> {
    const sid = newSessionId();
    const idHash = hashSessionId(sid);
    await this.sql`
      insert into bff.sessions
        (id_hash, sub, app_role, display_name, tokens_enc, access_expires_at, expires_at)
      values (${idHash}, ${session.sub}, ${session.appRole}, ${session.displayName},
              ${sealTokens(session.tokens, this.key, idHash)}, ${session.accessExpiresAt},
              now() + ${SESSION_LIFETIME}::interval)`;
    return sid;
  }

  /** The active session (not revoked, not expired) or null. */
  async find(sid: string): Promise<Session | null> {
    const [row] = await this.sql<Row[]>`
      select *, false as due from bff.sessions
      where id_hash = ${hashSessionId(sid)} and revoked_at is null and expires_at > now()`;
    return row ? this.toSession(row) : null;
  }

  /**
   * Returns the active session; refreshes its access token first if it is about to expire.
   * The row lock (`for update`) makes parallel requests wait, so only the first one calls
   * the IdP and the others read the new token. A failed refresh revokes the session.
   */
  async refreshIfDue(
    sid: string,
    refresh: (refreshToken: string) => Promise<Refreshed>,
  ): Promise<Session | null> {
    const idHash = hashSessionId(sid);
    return this.sql.begin(async (tx) => {
      const [row] = await tx<Row[]>`
        select *, access_expires_at < now() + ${REFRESH_MARGIN}::interval as due
        from bff.sessions
        where id_hash = ${idHash} and revoked_at is null and expires_at > now()
        for update`;
      if (!row) return null;
      const session = this.toSession(row);
      if (!session || !row.due) return session;

      let next: Refreshed;
      try {
        if (!session.tokens.refresh) throw new Error("no refresh token");
        next = await refresh(session.tokens.refresh);
      } catch {
        await tx`update bff.sessions set revoked_at = now() where id_hash = ${idHash}`;
        return null;
      }
      const tokens: TokenSet = {
        access: next.tokens.access,
        refresh: next.tokens.refresh ?? session.tokens.refresh,
        id: next.tokens.id ?? session.tokens.id,
      };
      await tx`
        update bff.sessions
        set tokens_enc = ${sealTokens(tokens, this.key, idHash)},
            access_expires_at = ${next.accessExpiresAt}
        where id_hash = ${idHash}`;
      return { ...session, tokens, accessExpiresAt: next.accessExpiresAt };
    });
  }

  /** Marks the session as revoked (kept for the record until it expires). */
  async revoke(sid: string): Promise<void> {
    await this.sql`update bff.sessions set revoked_at = now() where id_hash = ${hashSessionId(sid)}`;
  }

  /** Logout: the row is gone. */
  async delete(sid: string): Promise<void> {
    await this.sql`delete from bff.sessions where id_hash = ${hashSessionId(sid)}`;
  }

  /** Null if the tokens cannot be decrypted (manipulated row, wrong key). */
  private toSession(row: Row): Session | null {
    let tokens: TokenSet;
    try {
      tokens = openTokens(Buffer.from(row.tokens_enc), this.key, Buffer.from(row.id_hash));
    } catch {
      return null;
    }
    return {
      sub: row.sub,
      appRole: row.app_role,
      displayName: row.display_name,
      tokens,
      accessExpiresAt: row.access_expires_at,
      expiresAt: row.expires_at,
    };
  }
}
