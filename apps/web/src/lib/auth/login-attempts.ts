// Server-side half of the one-time login state (F01-AC5). The encrypted login cookie alone
// could be replayed by someone who stole it; this row can be used exactly once.
import { createHash } from "node:crypto";
import type postgres from "postgres";

const hashState = (state: string) => createHash("sha256").update(state).digest();

export class LoginAttempts {
  constructor(private readonly sql: postgres.Sql) {}

  /** Login route: remember the attempt for 10 minutes; old attempts are cleaned up. */
  async begin(state: string): Promise<void> {
    await this.sql`delete from bff.login_attempts where expires_at < now()`;
    await this.sql`
      insert into bff.login_attempts (state_hash, expires_at)
      values (${hashState(state)}, now() + interval '10 minutes')`;
  }

  /**
   * Callback: true exactly once per started attempt. The delete is atomic, so of several
   * parallel callbacks only one gets the row.
   */
  async consume(state: string): Promise<boolean> {
    const rows = await this.sql`
      delete from bff.login_attempts
      where state_hash = ${hashState(state)} and expires_at > now()
      returning 1`;
    return rows.length === 1;
  }
}
