import Link from "next/link";
import { Suspense } from "react";

import { RoleSwitcher } from "@/components/role-switcher";

// Screen 1 (the requirements map follows in F09).
export default function Home({ searchParams }: PageProps<"/">) {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-4 px-4 py-10">
      <h1 className="text-2xl font-semibold">Pflege-Posteingang</h1>
      <Suspense>
        <ExpiredHint searchParams={searchParams} />
      </Suspense>
      <p className="text-muted-foreground">
        Digitaler Posteingang einer Pflegeeinrichtung mit sicherer KI. Die Demo befindet sich im
        Aufbau.
      </p>
      <h2 className="text-lg font-semibold">Rolle wählen</h2>
      <p className="text-sm text-muted-foreground">
        Die Anmeldung läuft über einen echten Identity Provider (OIDC). Die Zugangsdaten der
        Demo-Konten sind öffentlich.
      </p>
      <RoleSwitcher />
      <Link href="/bewohner" className="underline">
        Zur Bewohnerliste
      </Link>
    </main>
  );
}

async function ExpiredHint({ searchParams }: Pick<PageProps<"/">, "searchParams">) {
  const { sitzung } = await searchParams;
  if (sitzung !== "abgelaufen") return null;
  return (
    <p role="alert" className="rounded-md border border-amber-400 bg-amber-50 px-3 py-2 text-sm">
      Sitzung abgelaufen – bitte Rolle wählen
    </p>
  );
}
