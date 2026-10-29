import Link from "next/link";
import { Suspense } from "react";

import { ApiStatusBoundary } from "@/components/api-status";
import { AttackFindings, type Finding } from "@/components/attack-findings";
import { NoAccess } from "@/components/no-access";
import { ReviewForm } from "@/components/review-form";
import { getAsCaller } from "@/lib/as-caller";
import type { MedicationChange, Suggestion } from "@/lib/documents/review";
import { STATUS_LABELS } from "@/lib/documents/labels";
import type { Resident } from "@/lib/residents";

type SuggestionAnswer = {
  status: string;
  suggestion: Suggestion | null;
  model: string | null;
  resident_candidate: string | null;
  medication_changes: MedicationChange[];
  diff_hash: string | null;
};

// Screen 3: check and approve (F03). Foreign and unknown documents look the same (F01-AC12).
export default function ReviewPage({ params }: PageProps<"/posteingang/[id]">) {
  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-4 px-4 py-6">
      <Link href="/posteingang" className="text-sm underline">
        ← Posteingang
      </Link>
      <Suspense fallback={<p className="text-muted-foreground">Lädt …</p>}>
        <Review params={params} />
      </Suspense>
    </main>
  );
}

async function Review({ params }: Pick<PageProps<"/posteingang/[id]">, "params">) {
  const { id } = await params;
  const result = await getAsCaller<SuggestionAnswer>(`/documents/${encodeURIComponent(id)}/suggestion`);
  if (result.status === 503) return <ApiStatusBoundary />;
  const answer = result.data;
  if (!answer) return <NoAccess />;
  if (answer.status !== "ready_for_review") {
    return (
      <section className="flex flex-col gap-2">
        <h1 className="text-2xl font-semibold">Dokument prüfen</h1>
        <p>Status: {STATUS_LABELS[answer.status] ?? answer.status} – hier gibt es nichts (mehr) zu prüfen.</p>
      </section>
    );
  }
  const residentsResult = await getAsCaller<Resident[]>("/residents");
  if (residentsResult.status === 503) return <ApiStatusBoundary />;
  const residents = residentsResult.data ?? [];
  // F07-AC6: findings of the injection check, shown above the fields.
  const details = await getAsCaller<{ screening_result: string | null; findings: Finding[] }>(
    `/documents/${encodeURIComponent(id)}`,
  );
  const findings = details.data?.findings ?? [];
  return (
    <section className="flex flex-col gap-3">
      <h1 className="text-2xl font-semibold">Dokument prüfen</h1>
      {findings.length > 0 && <AttackFindings findings={findings} />}
      <ReviewForm
        documentId={id}
        model={answer.model}
        suggestion={answer.suggestion}
        residents={residents}
        candidate={answer.resident_candidate}
        changes={answer.medication_changes}
        diffHash={answer.diff_hash}
      />
    </section>
  );
}
