// @vitest-environment node
// F01-AC1 (login_hint per role), F01-AC16 (same users as infra/demo-users.json), F01-AC19.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

import { DEMO_ROLES, isRoleKey, roleFromClaims } from "../roles";

const demoUsers = JSON.parse(
  readFileSync(join(__dirname, "../../../../../../infra/demo-users.json"), "utf8"),
);

describe("demo roles", () => {
  it("match infra/demo-users.json", () => {
    const fromFile = Object.fromEntries(
      demoUsers.users.map((u: { username: string; roles: string[] }) => [u.username, u.roles]),
    );
    for (const role of Object.values(DEMO_ROLES)) {
      expect(fromFile[role.username]).toEqual([role.idpRole]);
    }
    expect(Object.keys(DEMO_ROLES)).toHaveLength(demoUsers.users.length);
  });

  it("hold no password (F01-AC22): the public ones exist only as secrets", () => {
    for (const role of Object.values(DEMO_ROLES)) expect(role).not.toHaveProperty("password");
  });

  it("accepts only the three role keys", () => {
    expect(["wb1", "wb2", "pdl"].every(isRoleKey)).toBe(true);
    for (const value of [null, "", "admin", "WB1", "toString", "__proto__"]) {
      expect(isRoleKey(value)).toBe(false);
    }
  });
});

describe("roleFromClaims", () => {
  const ZITADEL = "urn:zitadel:iam:org:project:roles";

  it("reads the Zitadel object form", () => {
    expect(roleFromClaims({ [ZITADEL]: { nurse_wb2: { "1": "org" } } }, ZITADEL)).toBe("wb2");
  });

  it("reads the list form of other IdPs (test OIDC server)", () => {
    expect(roleFromClaims({ roles: ["nurse_wb1"] }, "roles")).toBe("wb1");
  });

  it("prefers pdl, like the API", () => {
    expect(roleFromClaims({ roles: ["nurse_wb1", "pdl"] }, "roles")).toBe("pdl");
  });

  it.each([{}, { roles: ["admin"] }, { roles: "pdl" }, { other: ["pdl"] }])(
    "returns null without a known role: %j",
    (claims) => {
      expect(roleFromClaims(claims, "roles")).toBeNull();
    },
  );
});
