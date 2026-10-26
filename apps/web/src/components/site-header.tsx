import Link from "next/link";

/**
 * Header with the signed-in role and a logout button (F01-AC20).
 * roleLabel: undefined while the session is still loading.
 */
export function SiteHeader({ roleLabel }: { roleLabel?: string | null }) {
  return (
    <header className="flex items-center justify-between gap-3 border-b px-4 py-2 text-sm">
      <Link href="/" className="font-semibold">
        Pflege-Posteingang
      </Link>
      {roleLabel ? (
        <div className="flex items-center gap-3">
          <span>{roleLabel}</span>
          {/* Plain form POST: a hard page change, so no client cache keeps old data (AC13). */}
          <form method="post" action="/auth/logout">
            <button type="submit" className="rounded-md border px-2 py-1 hover:bg-muted">
              Abmelden
            </button>
          </form>
        </div>
      ) : roleLabel === null ? (
        <span className="text-muted-foreground">Nicht angemeldet</span>
      ) : null}
    </header>
  );
}
