"use client";
// Screen 3: check, correct and approve the AI suggestion (F03). Only values with a source in
// the document are prefilled; the resident must be confirmed actively; the medication
// comparison comes from the server and is recomputed when resident or medications change.
import { useEffect, useRef, useState } from "react";

import { DOC_TYPE_LABELS } from "@/lib/documents/labels";
import {
  CHANGE_LABELS,
  SLOTS,
  foundValues,
  missingValues,
  type FollowUpValue,
  type MedicationChange,
  type MedicationValue,
  type Suggestion,
} from "@/lib/documents/review";
import { goTo, leaveEndedSession } from "@/lib/navigation";

export type ReviewProps = {
  documentId: string;
  model: string | null;
  suggestion: Suggestion | null;
  residents: { id: string; display_name: string }[];
  candidate: string | null;
  changes: MedicationChange[];
  diffHash: string | null;
};

const EMPTY_DOSE = { morgens: "0", mittags: "0", abends: "0", nachts: "0" };
const input = "w-full rounded-md border px-2 py-1";

async function postJson(url: string, body?: unknown) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (response.status === 401) leaveEndedSession();
  return { response, data: await response.json().catch(() => ({})) };
}

export function ReviewForm(props: ReviewProps) {
  const { documentId, suggestion } = props;
  const [view, setView] = useState<"original" | "fields">("fields");
  const [docType, setDocType] = useState(suggestion?.doc_type?.value ?? "sonstiges");
  const [documentDate, setDocumentDate] = useState(suggestion?.document_date?.value ?? "");
  const [diagnoses, setDiagnoses] = useState<string[]>(foundValues(suggestion?.diagnoses));
  const [medications, setMedications] = useState<MedicationValue[]>(foundValues(suggestion?.medications));
  const [followUps, setFollowUps] = useState<FollowUpValue[]>(foundValues(suggestion?.follow_ups));
  const [residentId, setResidentId] = useState(props.candidate ?? "");
  const [confirmed, setConfirmed] = useState(false);
  const [changes, setChanges] = useState(props.changes);
  const [diffHash, setDiffHash] = useState(props.diffHash);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const missing = missingValues(suggestion);

  // F03-AC6a: a new resident or other medications -> new comparison (debounced).
  const firstRender = useRef(true);
  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    const timer = setTimeout(async () => {
      if (!residentId) {
        setChanges([]);
        setDiffHash(null);
        return;
      }
      const { response, data } = await postJson(`/api/documents/${documentId}/medication-diff`, {
        resident_id: residentId,
        doc_type: docType,
        medications,
      });
      if (response.ok) {
        setChanges(data.medication_changes);
        setDiffHash(data.diff_hash);
      }
    }, 400);
    return () => clearTimeout(timer);
  }, [residentId, docType, medications, documentId]);

  function chooseResident(id: string) {
    setResidentId(id);
    setConfirmed(false); // a different resident must be confirmed again
    setDiffHash(null);
  }

  async function approve() {
    setBusy(true);
    setProblem(null);
    const { response, data } = await postJson(`/api/documents/${documentId}/approve`, {
      resident_id: residentId,
      resident_confirmed: confirmed,
      diff_hash: diffHash,
      doc_type: docType,
      document_date: documentDate || null,
      diagnoses: diagnoses.filter((d) => d.trim()),
      medications,
      follow_ups: followUps.map((f) => ({ title: f.title, due_date: f.due_date || null })),
    });
    setBusy(false);
    if (response.ok) return goTo(`/bewohner/${residentId}`);
    setProblem(data.message ?? "Freigabe nicht möglich.");
    if (data.error_code === "record_changed") {
      setChanges(data.medication_changes);
      setDiffHash(data.diff_hash);
    }
  }

  async function reject() {
    setBusy(true);
    const { response, data } = await postJson(`/api/documents/${documentId}/reject`);
    setBusy(false);
    if (response.ok) return goTo("/posteingang");
    setProblem(data.message ?? "Verwerfen nicht möglich.");
  }

  const toggle = (name: "original" | "fields", label: string) => (
    <button
      type="button"
      aria-pressed={view === name}
      onClick={() => setView(name)}
      className="flex-1 rounded-md border px-3 py-1 aria-pressed:bg-muted"
    >
      {label}
    </button>
  );

  return (
    <div className="flex flex-col gap-4">
      <div className="flex gap-2 md:hidden">
        {toggle("original", "Original")}
        {toggle("fields", "Felder")}
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <section className={view === "original" ? "block" : "hidden md:block"}>
          <iframe
            src={`/api/documents/${documentId}/file`}
            title="Originaldokument"
            className="h-[70vh] w-full rounded-lg border bg-white"
          />
        </section>

        <section className={`${view === "fields" ? "flex" : "hidden md:flex"} flex-col gap-4`}>
          <p className="rounded-md bg-amber-50 px-3 py-2 text-sm text-amber-950">
            <strong>KI-Vorschlag – bitte jedes Feld prüfen</strong>
            <br />
            Modell: {props.model ?? "–"}
          </p>
          {!suggestion && (
            <p className="text-sm font-medium">Kein Vorschlag möglich – bitte manuell erfassen</p>
          )}
          {missing.length > 0 && (
            <ul className="text-sm text-red-700">
              {missing.map((text, i) => (
                <li key={i}>nicht im Dokument gefunden: {text}</li>
              ))}
            </ul>
          )}

          <fieldset className="flex flex-col gap-2 rounded-lg border p-3">
            <label className="text-sm font-medium" htmlFor="resident">
              Bewohner
            </label>
            <select
              id="resident"
              aria-label="Bewohner"
              value={residentId}
              onChange={(event) => chooseResident(event.target.value)}
              className={input}
            >
              <option value="">– auswählen –</option>
              {props.residents.map((resident) => (
                <option key={resident.id} value={resident.id}>
                  {resident.display_name}
                </option>
              ))}
            </select>
            {!residentId && <p className="text-sm text-red-700">Bewohner bitte auswählen</p>}
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                aria-label="Bewohner bestätigen"
                checked={confirmed}
                disabled={!residentId}
                onChange={(event) => setConfirmed(event.target.checked)}
              />
              Bewohner bestätigen
            </label>
          </fieldset>

          <div className="grid gap-2 sm:grid-cols-2">
            <label className="text-sm">
              Dokumenttyp
              <select value={docType} onChange={(e) => setDocType(e.target.value)} className={input}>
                {Object.entries(DOC_TYPE_LABELS).map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            <label className="text-sm">
              Dokumentdatum
              <input type="date" value={documentDate} onChange={(e) => setDocumentDate(e.target.value)} className={input} />
            </label>
          </div>

          <ListSection
            title="Diagnosen"
            addLabel="Diagnose hinzufügen"
            items={diagnoses}
            onChange={setDiagnoses}
            empty=""
            render={(value, i, set) => (
              <input aria-label={`Diagnose ${i + 1}`} value={value} onChange={(e) => set(e.target.value)} className={input} />
            )}
            removeLabel={(i) => `Diagnose ${i + 1} entfernen`}
          />

          <ListSection
            title="Medikamente"
            addLabel="Medikament hinzufügen"
            items={medications}
            onChange={setMedications}
            empty={{ name: "", strength: "", dosage: { ...EMPTY_DOSE }, hint: null }}
            render={(med, i, set) => (
              <div className="grid grid-cols-6 gap-1">
                <input aria-label={`Medikament ${i + 1}`} value={med.name} onChange={(e) => set({ ...med, name: e.target.value })} className={`${input} col-span-3`} />
                <input aria-label={`Stärke ${i + 1}`} value={med.strength ?? ""} onChange={(e) => set({ ...med, strength: e.target.value })} className={`${input} col-span-3`} />
                {SLOTS.map((slot) => (
                  <input
                    key={slot}
                    aria-label={`${slot} ${i + 1}`}
                    value={med.dosage[slot] ?? ""}
                    onChange={(e) => set({ ...med, dosage: { ...med.dosage, [slot]: e.target.value } })}
                    className={`${input} text-center`}
                  />
                ))}
              </div>
            )}
            removeLabel={(i) => `Medikament ${i + 1} entfernen`}
          />

          <ListSection
            title="Wiedervorlagen"
            addLabel="Wiedervorlage hinzufügen"
            items={followUps}
            onChange={setFollowUps}
            empty={{ title: "", due_date: null }}
            render={(item, i, set) => (
              <div className="grid grid-cols-3 gap-1">
                <input aria-label={`Wiedervorlage ${i + 1}`} value={item.title} onChange={(e) => set({ ...item, title: e.target.value })} className={`${input} col-span-2`} />
                <input type="date" aria-label={`Fälligkeit ${i + 1}`} value={item.due_date ?? ""} onChange={(e) => set({ ...item, due_date: e.target.value })} className={input} />
              </div>
            )}
            removeLabel={(i) => `Wiedervorlage ${i + 1} entfernen`}
          />

          {changes.length > 0 && (
            <div className="flex flex-col gap-1">
              <h3 className="text-sm font-semibold">Medikationsabgleich mit der Akte</h3>
              <ul aria-label="Medikationsabgleich" className="divide-y rounded-lg border text-sm">
                {changes.map((change, i) => (
                  <li key={i} className="flex justify-between px-3 py-1">
                    <span>{change.name}</span>
                    <span className="rounded-full border px-2 text-xs">{CHANGE_LABELS[change.kind] ?? change.kind}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {problem && (
            <p role="alert" className="text-sm text-red-700">
              {problem}
            </p>
          )}
          <div className="flex gap-2">
            <button
              type="button"
              disabled={!confirmed || !residentId || !diffHash || busy}
              onClick={approve}
              className="flex-1 rounded-md bg-primary px-3 py-2 text-primary-foreground disabled:opacity-50"
            >
              Freigeben
            </button>
            <button type="button" disabled={busy} onClick={reject} className="rounded-md border px-3 py-2">
              Verwerfen
            </button>
          </div>
        </section>
      </div>
    </div>
  );
}

function ListSection<T>({
  title,
  addLabel,
  items,
  onChange,
  empty,
  render,
  removeLabel,
}: {
  title: string;
  addLabel: string;
  items: T[];
  onChange: (items: T[]) => void;
  empty: T;
  render: (item: T, index: number, set: (item: T) => void) => React.ReactNode;
  removeLabel: (index: number) => string;
}) {
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="text-sm font-semibold">{title}</legend>
      {items.map((item, i) => (
        <div key={i} className="flex items-start gap-1">
          <div className="flex-1">{render(item, i, (next) => onChange(items.map((old, j) => (j === i ? next : old))))}</div>
          <button
            type="button"
            aria-label={removeLabel(i)}
            onClick={() => onChange(items.filter((_, j) => j !== i))}
            className="rounded-md border px-2"
          >
            ×
          </button>
        </div>
      ))}
      <button type="button" onClick={() => onChange([...items, empty])} className="self-start text-sm underline">
        {addLabel}
      </button>
    </fieldset>
  );
}
