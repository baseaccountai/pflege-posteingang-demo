"use client";
// Content of the error pages (app/error.tsx, app/global-error.tsx): no technical details
// (they stay in the server log), a retry and the sample record, which works without the API.
import Link from "next/link";

import { Button } from "@/components/ui/button";

export function ErrorMessage({ reset }: { reset: () => void }) {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-4 px-4 py-10">
      <h1 className="text-2xl font-semibold">Etwas ist schiefgelaufen</h1>
      <p className="text-muted-foreground">
        Die Seite konnte nicht geladen werden. Bitte versuchen Sie es erneut.
      </p>
      <div className="flex flex-wrap items-center gap-4">
        <Button variant="outline" size="sm" onClick={reset}>
          Erneut versuchen
        </Button>
        <Link href="/muster" className="text-sm underline">
          Musterakte ansehen
        </Link>
      </div>
    </main>
  );
}
