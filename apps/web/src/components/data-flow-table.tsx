// F06-AC11, AC12: which AI provider sees which data - the honest version of "privacy".
const STEPS = [
  { step: "Texterkennung (OCR)", sees: "Original (Bild bzw. PDF)", local: "Docling auf dem eigenen Rechner" },
  { step: "Feldvorschlag", sees: "nur Platzhalter", local: "Ollama auf dem eigenen Rechner" },
  { step: "Suche (Embeddings)", sees: "nur Platzhalter", local: "Ollama auf dem eigenen Rechner" },
  { step: "Antwort auf Fragen", sees: "nur Platzhalter", local: "Ollama auf dem eigenen Rechner" },
];

export function DataFlowTable() {
  return (
    <section className="flex flex-col gap-2">
      <h2 className="text-lg font-semibold">Welche KI sieht welche Daten</h2>
      <div className="overflow-x-auto">
        <table aria-label="Welche KI sieht welche Daten" className="w-full text-left text-sm">
          <thead>
            <tr className="border-b">
              <th className="py-1 pr-3">Schritt</th>
              <th className="py-1 pr-3">Öffentlich (Mistral)</th>
              <th className="py-1">Lokal</th>
            </tr>
          </thead>
          <tbody>
            {STEPS.map((row) => (
              <tr key={row.step} className="border-b">
                <td className="py-1 pr-3">{row.step}</td>
                <td className="py-1 pr-3">{row.sees}</td>
                <td className="py-1">{row.local}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-muted-foreground text-sm">
        Platzhalter: Bewohner werden zu „Bewohner_K42“, ihre Geburtsdaten zu „Geburtsdatum_K42“,
        Ärztinnen und Ärzte zu „Person_1“, Telefonnummern zu „[TELEFON_1]“. Die Zuordnung bleibt
        im Backend. Grenze: Namen ohne Anrede oder Titel, die nirgends bekannt sind, werden nicht
        erkannt.
      </p>
    </section>
  );
}
