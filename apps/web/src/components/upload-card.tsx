"use client";
// Upload card of the inbox (F02-AC1 to AC4, AC12). The photo is made smaller in the
// browser first; the server checks type, size and pages again and has the final word.
import { useState, useSyncExternalStore } from "react";

import { prepareUpload } from "@/lib/image/downscale";

export type UploadedDocument = { id: string; status: string };

const UPLOAD_NOTICE = "Bitte keine echten Personendaten hochladen.";

// false in the server HTML and during hydration, true once React runs in the browser.
const subscribeNever = () => () => {};

export function UploadCard({
  onUploaded,
  wards,
}: {
  onUploaded: (doc: UploadedDocument) => void;
  /** Only for the PDL: the wards she may choose from. */
  wards?: string[];
}) {
  const [ward, setWard] = useState(wards?.[0] ?? "");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  // Until React has taken over the page, a chosen file would be lost silently (slow phones):
  // the inputs stay disabled until then.
  const ready = useSyncExternalStore(subscribeNever, () => true, () => false);

  async function send(input: HTMLInputElement) {
    const original = input.files?.[0];
    input.value = ""; // the same file can be chosen again after an error
    if (!original) return;
    setBusy(true);
    setProblem(null);
    try {
      const body = new FormData();
      body.set("file", await prepareUpload(original));
      if (wards) body.set("ward_id", ward);
      const response = await fetch("/api/documents", { method: "POST", body });
      const answer = await response.json().catch(() => ({}));
      if (response.ok) onUploaded(answer as UploadedDocument);
      else setProblem(answer.message ?? "Upload fehlgeschlagen – bitte erneut versuchen.");
    } catch {
      setProblem("Upload fehlgeschlagen – bitte erneut versuchen.");
    } finally {
      setBusy(false);
    }
  }

  const button = "flex-1 cursor-pointer rounded-md border px-3 py-2 text-center hover:bg-muted";
  return (
    <section className="flex flex-col gap-3 rounded-lg border p-4" aria-busy={busy}>
      <p className="rounded-md bg-amber-50 px-3 py-2 text-sm font-medium text-amber-950">
        {UPLOAD_NOTICE}
      </p>
      {wards && (
        <label className="flex items-center gap-2 text-sm">
          Wohnbereich
          <select
            aria-label="Wohnbereich"
            value={ward}
            onChange={(event) => setWard(event.target.value)}
            className="rounded-md border px-2 py-1"
          >
            {wards.map((id) => (
              <option key={id} value={id}>
                {id.toUpperCase()}
              </option>
            ))}
          </select>
        </label>
      )}
      <div className="flex flex-col gap-2 sm:flex-row">
        <label className={button}>
          Foto aufnehmen
          <input
            type="file"
            aria-label="Foto aufnehmen"
            accept="image/jpeg,image/png"
            capture="environment"
            className="sr-only"
            disabled={busy || !ready}
            onChange={(event) => send(event.currentTarget)}
          />
        </label>
        <label className={button}>
          Datei hochladen
          <input
            type="file"
            aria-label="Datei hochladen"
            accept="image/jpeg,image/png,application/pdf"
            className="sr-only"
            disabled={busy || !ready}
            onChange={(event) => send(event.currentTarget)}
          />
        </label>
      </div>
      {busy && <p className="text-sm text-muted-foreground">Wird hochgeladen …</p>}
      {problem && (
        <p role="alert" className="text-sm text-red-700">
          {problem}
        </p>
      )}
    </section>
  );
}
