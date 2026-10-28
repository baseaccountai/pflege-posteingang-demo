import Link from "next/link";

// Unknown address (F10-AC4: within the root layout, with banner and footer).
export default function NotFound() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-4 px-4 py-10">
      <h1 className="text-2xl font-semibold">Seite nicht gefunden</h1>
      <p className="text-muted-foreground">Diese Adresse gibt es in der Demo nicht.</p>
      <Link href="/" className="underline">
        Zur Startseite
      </Link>
    </main>
  );
}
