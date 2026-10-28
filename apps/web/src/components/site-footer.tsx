/**
 * Disclaimer: independent application demo, not a product of Hochschule Anhalt - and the
 * nightly reset (F10-AC15), so nobody expects their uploads to stay.
 */
export function SiteFooter() {
  return (
    <footer className="mt-auto flex flex-col gap-1 border-t px-4 py-3 text-center text-xs text-muted-foreground">
      <p data-testid="disclaimer">
        Unabhängige Bewerbungsdemo, inspiriert von KLARA — kein Produkt der Hochschule Anhalt
      </p>
      <p>Alle Daten werden jede Nacht um 3 Uhr auf die Musterdaten zurückgesetzt.</p>
    </footer>
  );
}
