"use client";
// F05-AC1a: can this document already be asked about? After a failed indexing the record
// offers a retry; the approval itself is valid either way.
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { goTo, leaveEndedSession } from "@/lib/navigation";

export function SearchState({
  documentId,
  residentId,
  status,
  sample = false,
}: {
  documentId: string;
  residentId: string;
  status: string | null | undefined;
  sample?: boolean;
}) {
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  if (status === "pending") {
    return <span className="text-muted-foreground text-xs">wird für Fragen vorbereitet …</span>;
  }
  if (status !== "failed") return null;

  async function retry() {
    setBusy(true);
    setProblem(null);
    const response = await fetch(`/api/documents/${encodeURIComponent(documentId)}/reindex`, { method: "POST" });
    if (response.status === 401) return leaveEndedSession();
    if (response.ok) return goTo(`/bewohner/${residentId}`);
    const data = await response.json().catch(() => ({}));
    setProblem(data.message ?? "Neuversuch nicht möglich.");
    setBusy(false);
  }

  return (
    <span className="flex flex-wrap items-center gap-2 text-xs text-amber-900">
      noch nicht durchsuchbar
      {!sample && (
        <Button variant="outline" size="sm" disabled={busy} onClick={retry}>
          Erneut versuchen
        </Button>
      )}
      {problem && (
        <span role="alert" className="text-destructive">
          {problem}
        </span>
      )}
    </span>
  );
}
