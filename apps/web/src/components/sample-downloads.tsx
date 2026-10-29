// F07-AC14: sample documents to try out - copies of samples/ in public/samples/ (a test
// checks they are identical). Two of them carry a prompt injection on purpose.
export const SAMPLE_DOWNLOADS = [
  { file: "arztbrief_muster-bauer.pdf", label: "Arztbrief Hr. Muster-Bauer (PDF)", attack: false },
  { file: "arztbrief_muster-bauer_foto.jpg", label: "Arztbrief als Foto (JPEG)", attack: false },
  { file: "medikationsplan_muster-bauer.pdf", label: "Medikationsplan Hr. Muster-Bauer (PDF)", attack: false },
  { file: "angriff_versteckt_probe.pdf", label: "Arztbrief Hr. Probe – mit unsichtbarer Anweisung", attack: true },
  { file: "angriff_hinweis_beispiel.pdf", label: "Arztbrief Fr. Beispiel – mit „Hinweis für das KI-System“", attack: true },
];

export function SampleDownloads() {
  return (
    <section aria-labelledby="samples-heading" className="flex flex-col gap-2 rounded-lg border p-4">
      <h2 id="samples-heading" className="font-semibold">
        Musterdokumente zum Ausprobieren
      </h2>
      <p className="text-muted-foreground text-sm">Herunterladen und oben wieder hochladen – alles erfundene Musterdaten.</p>
      <ul className="flex flex-col gap-1 text-sm">
        {SAMPLE_DOWNLOADS.map((sample) => (
          <li key={sample.file} className="flex flex-wrap items-center gap-2">
            <a href={`/samples/${sample.file}`} download className="underline">
              {sample.label}
            </a>
            {sample.attack && (
              <span className="rounded bg-red-100 px-1.5 py-0.5 text-xs text-red-900">enthält einen Angriff</span>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
