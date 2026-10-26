import Link from "next/link";

// Shown when a login callback is rejected (F01-AC5); no details about the reason.
export default function LoginErrorPage() {
  return (
    <main className="mx-auto flex w-full max-w-3xl flex-1 flex-col gap-4 px-4 py-10">
      <h1 className="text-2xl font-semibold">Anmeldung fehlgeschlagen</h1>
      <p className="text-muted-foreground">
        Die Anmeldung konnte nicht abgeschlossen werden. Bitte starten Sie sie erneut.
      </p>
      <Link href="/" className="underline">
        Zur Startseite
      </Link>
    </main>
  );
}
