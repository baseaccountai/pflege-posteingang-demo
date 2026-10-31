// F08-AC2, ADR 0012: how the agent gets its own token, as the API reports it.
import type { AgentTokenWay as Way } from "@/lib/api";
import { repoHref } from "@/content/requirements-map";

const TEXT: Record<Way, string> = {
  exchange:
    "Token Exchange (RFC 8693) bei Zitadel: Der Identity Provider tauscht das Token der Pflegekraft gegen ein Agenten-Token (sub = Pflegekraft, act = Agent) und protokolliert jede Delegation.",
  self_signed:
    "Rückfall: Die API stellt das Agenten-Token selbst aus (eigener Schlüssel, 5 Minuten). Schwächer als der Token Exchange, weil die API sich selbst bestätigt.",
  off: "Der Agent ist zurzeit nicht eingerichtet.",
};

export function AgentTokenWay({ way }: { way: Way | null }) {
  return (
    <p data-testid="agent-token-way" className="text-sm">
      <span className="font-medium">Agenten-Token: </span>
      {way ? TEXT[way] : "Der aktive Weg ist gerade nicht abrufbar."}{" "}
      <a href={repoHref("docs/architecture/adr/0012-agent-token.md")} target="_blank" rel="noopener" className="underline">
        ADR 0012
      </a>
    </p>
  );
}
