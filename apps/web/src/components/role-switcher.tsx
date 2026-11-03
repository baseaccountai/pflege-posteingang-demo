"use client";
// Role buttons with the demo user names (F01-AC2); the password is never shown (F01-AC22). A switch is a plain form POST to
// /auth/logout?next=/auth/login?role=…: the old session is revoked and deleted on the server,
// then the IdP asks for the new credentials (F01-AC13). No client-side routing.
import { useState } from "react";

import { announceSessionEnd } from "@/components/session-sync";
import { DEMO_ROLES, type RoleKey } from "@/lib/auth/roles";

function CopyField({ label, value }: { label: string; value: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-muted-foreground">{label}:</span>
      <code className="flex-1 truncate">{value}</code>
      <button
        type="button"
        aria-label={`${label} kopieren`}
        className="rounded-md border px-2 py-0.5 text-xs hover:bg-muted"
        onClick={async () => {
          await navigator.clipboard.writeText(value);
          setCopied(true);
        }}
      >
        {copied ? "Kopiert" : "Kopieren"}
      </button>
    </div>
  );
}

export function RoleSwitcher() {
  return (
    <div className="grid gap-3 sm:grid-cols-3">
      {(Object.keys(DEMO_ROLES) as RoleKey[]).map((key) => {
        const role = DEMO_ROLES[key];
        const next = `/auth/login?role=${key}`;
        return (
          <section
            key={key}
            role="group"
            aria-label={role.label}
            className="flex flex-col gap-2 rounded-lg border p-3 text-sm"
          >
            <h3 className="font-semibold">{role.label}</h3>
            <CopyField label="Benutzername" value={role.username} />
            <p className="text-muted-foreground">Passwort: steht in der Bewerbung (lokal: README)</p>
            <form
              method="post"
              action={`/auth/logout?next=${encodeURIComponent(next)}`}
              onSubmit={announceSessionEnd}
            >
              <button
                type="submit"
                className="w-full rounded-md bg-primary px-3 py-1.5 text-primary-foreground hover:bg-primary/80"
              >
                Als {role.label} anmelden
              </button>
            </form>
          </section>
        );
      })}
    </div>
  );
}
