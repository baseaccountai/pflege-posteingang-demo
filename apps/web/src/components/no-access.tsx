import Link from "next/link";

/** Screen 8: same page for foreign and unknown residents, so nothing leaks (F01-AC12). */
export function NoAccess() {
  return (
    <section className="flex flex-col gap-3">
      <h1 className="text-2xl font-semibold">Nicht gefunden oder kein Zugriff</h1>
      <p className="text-muted-foreground">
        Diese Akte gibt es nicht, oder sie gehört zu einem Wohnbereich, für den Ihre Rolle keine
        Rechte hat. Die Datenbank gibt fremde Wohnbereiche gar nicht erst heraus (Row Level
        Security), deshalb lässt sich beides nicht unterscheiden.
      </p>
      <Link href="/bewohner" className="underline">
        Zur Bewohnerliste
      </Link>
    </section>
  );
}
