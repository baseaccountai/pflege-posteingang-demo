// The three demo roles (same users as infra/demo-users.json, checked by a test).
// The role decides only the login_hint and the label; access rights are derived again by
// the API from the access token (apps/api/app/auth/claims.py).

export const DEMO_ROLES = {
  wb1: { username: "pflege-wb1", idpRole: "nurse_wb1", label: "Pflegekraft WB1" },
  wb2: { username: "pflege-wb2", idpRole: "nurse_wb2", label: "Pflegekraft WB2" },
  pdl: { username: "pdl", idpRole: "pdl", label: "Pflegedienstleitung" },
} as const;

export type RoleKey = keyof typeof DEMO_ROLES;

export function isRoleKey(value: unknown): value is RoleKey {
  return typeof value === "string" && Object.hasOwn(DEMO_ROLES, value);
}

/**
 * Role from the ID token's roles claim (name from OIDC_ROLES_CLAIM). Zitadel sends an
 * object {"nurse_wb1": {...}}, other IdPs a list. PDL wins, like in the API.
 */
export function roleFromClaims(claims: Record<string, unknown>, claimName: string): RoleKey | null {
  const value = claims[claimName];
  const names = Array.isArray(value)
    ? value.filter((v) => typeof v === "string")
    : value && typeof value === "object"
      ? Object.keys(value)
      : [];
  const keys = (Object.keys(DEMO_ROLES) as RoleKey[]).filter((key) =>
    names.includes(DEMO_ROLES[key].idpRole),
  );
  return keys.includes("pdl") ? "pdl" : (keys[0] ?? null);
}
