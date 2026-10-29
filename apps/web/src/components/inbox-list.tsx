"use client";
// Inbox list (F02-AC13) with live status (polling every 3 s while something runs, F02-AC6)
// and "Erneut versuchen" for failed documents (F02-AC8). Only the BFF is called; RLS in the
// database decides which documents appear.
import Link from "next/link";
import { useEffect, useState } from "react";

import { DOC_TYPE_LABELS, STATUS_LABELS, errorMessage, isPending } from "@/lib/documents/labels";
import { leaveEndedSession } from "@/lib/navigation";

export type InboxDocument = {
  id: string;
  ward_id: string;
  doc_type: string | null;
  status: string;
  error_code: string | null;
  created_at: string;
  screening_result?: string | null; // F07: clean | suspicious | not_screened
};

const POLL_MS = 3000;

async function loadInbox(): Promise<InboxDocument[] | null> {
  const response = await fetch("/api/documents", { cache: "no-store" });
  if (response.status === 401) {
    leaveEndedSession();
    return null;
  }
  return response.ok ? ((await response.json()) as InboxDocument[]) : null;
}

const time = (iso: string) =>
  new Date(iso).toLocaleTimeString("de-DE", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Europe/Berlin",
  });

export function InboxList({
  documents,
  onChange,
}: {
  documents: InboxDocument[];
  onChange: (documents: InboxDocument[]) => void;
}) {
  const [problem, setProblem] = useState<string | null>(null);
  const running = documents.some((doc) => isPending(doc.status));

  useEffect(() => {
    if (!running) return;
    const timer = setInterval(async () => {
      const fresh = await loadInbox();
      if (fresh) onChange(fresh);
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [running, onChange]);

  async function retry(id: string) {
    setProblem(null);
    const response = await fetch(`/api/documents/${id}/retry`, { method: "POST" });
    if (!response.ok) {
      const answer = await response.json().catch(() => ({}));
      setProblem(answer.message ?? "Neuversuch nicht möglich.");
      return;
    }
    const fresh = await loadInbox();
    if (fresh) onChange(fresh);
  }

  if (documents.length === 0) {
    return <p className="text-muted-foreground">Noch keine Dokumente.</p>;
  }
  return (
    <div className="flex flex-col gap-2">
      {problem && (
        <p role="alert" className="text-sm text-red-700">
          {problem}
        </p>
      )}
      <ul className="divide-y rounded-lg border">
        {documents.map((doc) => (
          <li key={doc.id} data-testid={`document-${doc.id}`} className="flex flex-col gap-1 px-3 py-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm text-muted-foreground">{time(doc.created_at)}</span>
              <span className="font-medium">{doc.doc_type ? DOC_TYPE_LABELS[doc.doc_type] : "Dokument"}</span>
              <span className="rounded-full border px-2 py-0.5 text-xs">{STATUS_LABELS[doc.status] ?? doc.status}</span>
              {doc.screening_result === "suspicious" && (
                <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs font-medium text-red-900">verdächtig</span>
              )}
              <span className="text-xs text-muted-foreground">{doc.ward_id.toUpperCase()}</span>
              {doc.status === "ready_for_review" && (
                <Link href={`/posteingang/${doc.id}`} className="ml-auto underline">
                  Prüfen
                </Link>
              )}
              {doc.status === "failed" && (
                <button
                  type="button"
                  onClick={() => retry(doc.id)}
                  className="ml-auto rounded-md border px-2 py-0.5 text-sm hover:bg-muted"
                >
                  Erneut versuchen
                </button>
              )}
            </div>
            {errorMessage(doc.error_code) && (
              <p className="text-sm text-red-700">{errorMessage(doc.error_code)}</p>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
