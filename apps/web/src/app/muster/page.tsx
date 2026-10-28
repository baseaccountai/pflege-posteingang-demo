import type { Metadata } from "next";
import Link from "next/link";
import { Suspense } from "react";

import { SampleRecordSection } from "@/components/sample-record-section";

export const metadata: Metadata = { title: "Musterakte · Pflege-Posteingang" };

// F10-AC14: public, static sample record - no login, no API.
export default function SampleRecordPage() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-4 px-4 py-10">
      <p className="rounded-md border border-sky-300 bg-sky-50 px-3 py-2 text-sm text-sky-950">
        Statische Musterakte aus den Musterdaten – ohne Anmeldung und ohne Server ansehbar. Zum
        Ausprobieren der Demo{" "}
        <Link href="/" className="underline">
          eine Rolle wählen
        </Link>
        .
      </p>
      <Suspense fallback={<p className="text-muted-foreground">Lädt …</p>}>
        <SampleRecordSection />
      </Suspense>
    </main>
  );
}
