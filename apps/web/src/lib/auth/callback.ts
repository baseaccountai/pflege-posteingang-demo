// Callback logic (F01-AC3, F01-AC5), separate from the route handler so it can be tested.
import type { LoginState } from "./login-state";
import type { NewSession } from "./session-store";

type Deps = {
  consume: (state: string) => Promise<boolean>;
  finish: (state: LoginState) => Promise<NewSession>;
  create: (session: NewSession) => Promise<string>;
};

/**
 * Returns the new session id, or null on any failure. The server-side attempt is used up
 * BEFORE the code is redeemed: a replay never reaches the IdP's token endpoint.
 */
export async function completeLogin(state: LoginState | null, deps: Deps): Promise<string | null> {
  if (!state) return null;
  if (!(await deps.consume(state.state))) {
    console.warn("login callback rejected: attempt unknown, used or expired");
    return null;
  }
  try {
    return await deps.create(await deps.finish(state));
  } catch (error) {
    // Wrong state/nonce/PKCE, reused or expired code, IdP error, no known role.
    // Logged without details: messages could contain parts of the request.
    console.warn("login callback rejected:", (error as Error).name);
    return null;
  }
}
