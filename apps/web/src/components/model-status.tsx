// F10-AC16: whether the AI provider answers right now, as the API reports it - so a failed
// request can be told apart from an outage of the provider.
import type { ModelStatus as Status } from "@/lib/api";

const TEXT: Record<Status, string> = {
  ok: "erreichbar",
  unavailable: "gestört – Anfragen an die KI scheitern gerade, bitte später erneut versuchen",
};

export function ModelStatus({ status }: { status: Status | null }) {
  return (
    <p data-testid="model-status" className="text-sm">
      <span className="font-medium">KI-Anbieter: </span>
      {status ? TEXT[status] : "Zustand gerade nicht abrufbar"}
    </p>
  );
}
