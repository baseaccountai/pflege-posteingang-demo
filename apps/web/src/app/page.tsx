import Link from "next/link";
import { Suspense } from "react";

import { ProjectCard } from "@/components/project-card";
import { RequirementsMap } from "@/components/requirements-map";
import { RoleSwitcher } from "@/components/role-switcher";

// Screen 1 (F09): what this is, where the job ad's requirements are met, then the roles.
// Renders without API and database (F09-AC7): only static content and the role buttons.
export default function Home({ searchParams }: PageProps<"/">) {
  return (
    <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-6 px-4 py-10">
      <h1 className="text-2xl font-semibold">Pflege-Posteingang</h1>
      <Suspense>
        <ExpiredHint searchParams={searchParams} />
      </Suspense>
      <ProjectCard />
      <RequirementsMap />
      <section aria-labelledby="roles-heading" className="flex flex-col gap-3">
        <h2 id="roles-heading" className="text-lg font-semibold">
          Rolle wählen
        </h2>
        <p className="text-sm text-muted-foreground">
          Alle Personen und Dokumente sind erfundene Musterdaten. Die Anmeldung läuft über einen
          echten Identity Provider (OIDC). Die Passwörter der Demo-Konten stehen in der
          Bewerbung, damit nicht jeder die Tageskontingente der Demo aufbrauchen kann.
        </p>
        <RoleSwitcher />
        <Link href="/muster" className="text-sm underline">
          Ohne Anmeldung: Musterakte ansehen
        </Link>
      </section>
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
