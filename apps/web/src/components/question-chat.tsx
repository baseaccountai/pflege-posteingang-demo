"use client";
// Screen 4 (F05): questions about the documents of the own wards, answered with sources.
// The conversation lives only in this component's state - not in localStorage, not on the
// server - so a role switch (a full page change) leaves nothing behind (F05-AC11).
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { formatDate } from "@/lib/dates";
import { DOC_TYPE_LABELS } from "@/lib/documents/labels";
import { documentFileHref } from "@/lib/documents/file-href";
import { modelLabel } from "@/lib/models";
import { leaveEndedSession } from "@/lib/navigation";

const MAX_LENGTH = 500;

type Source = {
  document_id: string;
  doc_type: string | null;
  document_date: string | null;
  resident_name: string;
  page: number;
};
type Exchange = { question: string; answer: string; sources: Source[]; model: string };

function sourceLabel(source: Source): string {
  const type = (source.doc_type && DOC_TYPE_LABELS[source.doc_type]) || "Dokument";
  const date = source.document_date ? ` vom ${formatDate(source.document_date)}` : "";
  return `${type}${date} · ${source.resident_name} · Seite ${source.page}`;
}

export function QuestionChat({
  residents,
  initialResident,
}: {
  residents: { id: string; display_name: string }[];
  initialResident: string;
}) {
  const [resident, setResident] = useState(initialResident);
  const [question, setQuestion] = useState("");
  const [history, setHistory] = useState<Exchange[]>([]);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  async function ask(event: React.FormEvent) {
    event.preventDefault();
    const text = question.trim();
    if (!text) return;
    setBusy(true);
    setProblem(null);
    try {
      const response = await fetch("/api/questions", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify(resident ? { question: text, resident_id: resident } : { question: text }),
      });
      if (response.status === 401) return leaveEndedSession();
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        setProblem(data.message ?? "Die Frage konnte nicht gestellt werden.");
        return;
      }
      setHistory((before) => [...before, { question: text, answer: data.answer, sources: data.sources, model: data.model }]);
      setQuestion("");
    } catch {
      setProblem("Die Frage konnte nicht gestellt werden.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <ol className="flex flex-col gap-3">
        {history.map((exchange, index) => (
          <li key={index} data-testid={`answer-${index}`} className="flex flex-col gap-2 rounded-lg border p-3">
            <p className="font-medium">{exchange.question}</p>
            <p className="whitespace-pre-line">{exchange.answer}</p>
            {exchange.sources.length > 0 && (
              <ul className="flex flex-wrap gap-2" aria-label="Quellen">
                {exchange.sources.map((source, i) => (
                  <li key={i}>
                    <a
                      href={documentFileHref(source.document_id)}
                      target="_blank"
                      rel="noopener"
                      className="rounded-full border px-2 py-0.5 text-xs underline"
                    >
                      [Q{i + 1}] {sourceLabel(source)}
                    </a>
                  </li>
                ))}
              </ul>
            )}
            <p className="text-muted-foreground text-xs">Antwort von {modelLabel(exchange.model)} · KI-Antwort, bitte an der Quelle prüfen</p>
          </li>
        ))}
      </ol>

      {problem && (
        <p role="alert" className="text-destructive text-sm">
          {problem}
        </p>
      )}

      <form onSubmit={ask} className="flex flex-col gap-2 rounded-lg border p-3">
        <label className="flex flex-col gap-1 text-sm">
          Bewohner
          <select
            aria-label="Bewohner"
            value={resident}
            onChange={(event) => setResident(event.target.value)}
            className="rounded-md border px-2 py-1"
          >
            <option value="">Alle Bewohner meines Wohnbereichs</option>
            {residents.map((r) => (
              <option key={r.id} value={r.id}>
                {r.display_name}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          Frage
          <textarea
            aria-label="Frage"
            value={question}
            maxLength={MAX_LENGTH}
            rows={3}
            onChange={(event) => setQuestion(event.target.value)}
            className="rounded-md border px-2 py-1"
          />
        </label>
        <div className="flex items-center justify-between gap-2">
          <span className="text-muted-foreground text-xs">
            {question.length}/{MAX_LENGTH}
          </span>
          <Button type="submit" disabled={busy || !question.trim()}>
            Fragen
          </Button>
        </div>
      </form>
    </div>
  );
}
