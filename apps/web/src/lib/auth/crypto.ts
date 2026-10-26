// AES-256-GCM for everything the BFF keeps away from the browser in readable form:
// tokens in bff.sessions and the login state cookie. Key: SESSION_ENC_KEY.
import { createCipheriv, createDecipheriv, randomBytes } from "node:crypto";

const VERSION = 1; // first byte, allows a later key/format change
const IV_BYTES = 12;
const TAG_BYTES = 16;

/** SESSION_ENC_KEY: 32 random bytes, base64 (e.g. `openssl rand -base64 32`). */
export function parseEncKey(value: string | undefined): Buffer {
  const key = Buffer.from(value ?? "", "base64");
  if (key.length !== 32) throw new Error("SESSION_ENC_KEY must be 32 bytes, base64-encoded");
  return key;
}

/**
 * Layout: version (1) | iv (12) | ciphertext | tag (16).
 * `aad` is authenticated, not encrypted: the data only opens in the same context.
 */
export function sealJson(value: unknown, key: Buffer, aad: Buffer): Buffer {
  const iv = randomBytes(IV_BYTES);
  const cipher = createCipheriv("aes-256-gcm", key, iv);
  cipher.setAAD(aad);
  const body = Buffer.concat([cipher.update(JSON.stringify(value), "utf8"), cipher.final()]);
  return Buffer.concat([Buffer.from([VERSION]), iv, body, cipher.getAuthTag()]);
}

/** Throws if the data was changed, belongs to another context or another key. */
export function openJson<T>(sealed: Buffer, key: Buffer, aad: Buffer): T {
  if (sealed.length < 1 + IV_BYTES + TAG_BYTES || sealed[0] !== VERSION) {
    throw new Error("unknown format");
  }
  const iv = sealed.subarray(1, 1 + IV_BYTES);
  const tag = sealed.subarray(sealed.length - TAG_BYTES);
  const decipher = createDecipheriv("aes-256-gcm", key, iv);
  decipher.setAAD(aad);
  decipher.setAuthTag(tag);
  const body = sealed.subarray(1 + IV_BYTES, sealed.length - TAG_BYTES);
  return JSON.parse(Buffer.concat([decipher.update(body), decipher.final()]).toString("utf8"));
}
