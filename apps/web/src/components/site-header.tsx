import Link from "next/link";

import { LogoutForm } from "@/components/session-sync";

/**
 * Header with the link to the project description (F09-AC2), the signed-in role and a
 * logout button (F01-AC20).
 * roleLabel: undefined while the session is still loading.
 */
export function SiteHeader({ roleLabel }: { roleLabel?: string | null }) {
  return (
    <header className="flex flex-wrap items-center justify-between gap-3 border-b px-4 py-2 text-sm">
      <div className="flex flex-wrap items-center gap-3">
        <Link href="/" className="font-semibold">
          Pflege-Posteingang
        </Link>
        {/* F09-AC2: on every page, signed in or not. */}
        <Link href="/projekt" className="underline">
          Über das Projekt
        </Link>
      </div>
      {roleLabel ? (
        <div className="flex flex-wrap items-center justify-end gap-3">
          <nav className="flex gap-3">
            <Link href="/posteingang" className="underline">
              Posteingang
            </Link>
            <Link href="/bewohner" className="underline">
              Bewohner
            </Link>
            <Link href="/fragen" className="underline">
              Fragen
            </Link>
          </nav>
          <span>{roleLabel}</span>
          {/* Plain form POST: a hard page change, so no client cache keeps old data (AC13). */}
          <LogoutForm className="rounded-md border px-2 py-1 hover:bg-muted">Abmelden</LogoutForm>
        </div>
      ) : roleLabel === null ? (
        <span className="text-muted-foreground">Nicht angemeldet</span>
      ) : null}
    </header>
  );
}
