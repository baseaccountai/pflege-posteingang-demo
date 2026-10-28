// F09-AC1: the first thing on the start page - what this is, in one sentence.
import Link from "next/link";

export function ProjectCard() {
  return (
    <section aria-label="Über das Projekt" className="flex flex-col gap-2 rounded-lg border border-teal-200 bg-teal-50 p-4 text-teal-950">
      <p>
        <strong>Pflege-Posteingang</strong> ist eine Bewerbungsdemo: ein digitaler Posteingang für
        Pflegeeinrichtungen, in dem KI Arztbriefe und Medikationspläne liest, Pflegekräfte jeden
        Vorschlag prüfen und Fragen nur mit belegten Quellen beantwortet werden – sicher getrennt
        nach Wohnbereichen.
      </p>
      <Link href="/projekt" className="self-start text-sm font-medium underline">
        Mehr über das Projekt
      </Link>
    </section>
  );
}
