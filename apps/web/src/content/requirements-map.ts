// F09: the requirements of the job ad ("Sie verfügen über …", design section 1) and where
// this demo shows them - the single source of the requirements map on the start page.
// A test checks that every app link is a route and every repo path exists (F09-AC5).

export type RequirementEntry = {
  id: string;
  text: string;
  level: "gefordert" | "wuenschenswert";
  /** How the demo meets it, in one or two sentences. */
  how: string;
  /** Where to see it in the app; none while the feature is still to come (F09-AC4). */
  appHref?: string;
  appLabel?: string;
  /** Files or folders in the repository; a folder ends with "/". */
  repoPaths: string[];
  status: "live" | "stufe2";
  /** Shows the link to the injection report (or "folgt") - F13-AC7. */
  showsSecurityReport?: boolean;
};

/**
 * F13-AC7: the measured injection report, set by the commit that adds it
 * (`make security-report` writes docs/security/reports/<date>-injection.md). null: not yet.
 */
export const SECURITY_REPORT: string | null = "docs/security/reports/2026-10-31-injection.md";

export const DEFAULT_REPO_URL = "https://github.com/baseaccountai/pflege-posteingang-demo";

/** GitHub link to a file (blob) or folder (tree, path ends with "/") on main. */
export function repoHref(repoPath: string, repoUrl = process.env.NEXT_PUBLIC_REPO_URL || DEFAULT_REPO_URL): string {
  return `${repoUrl}/${repoPath.endsWith("/") ? "tree" : "blob"}/main/${repoPath}`;
}

export const REQUIREMENTS: RequirementEntry[] = [
  {
    id: "architecture",
    text: "Softwarearchitektur, Web-Backend (Python/TypeScript)",
    level: "gefordert",
    how:
      "Next.js als Backend-for-Frontend (TypeScript) und FastAPI (Python) mit Postgres; " +
      "Architektur nach arc42 mit Entscheidungen als ADRs, jedes Feature als Spec mit Akzeptanzkriterien.",
    repoPaths: ["docs/architecture/", "apps/api/", "apps/web/"],
    status: "live",
  },
  {
    id: "llm-apis",
    text: "Anbindung von LLMs über APIs",
    level: "gefordert",
    how:
      "Mistral OCR liest Fotos und PDFs, Mistral Small schlägt Felder mit wörtlichen Belegen vor; " +
      "Anbieter per Konfiguration austauschbar, Kosten durch Tageskontingente begrenzt.",
    appHref: "/posteingang",
    appLabel: "Posteingang",
    repoPaths: ["apps/api/app/providers/", "apps/api/app/extraction/"],
    status: "live",
  },
  {
    id: "rag-agents",
    text: "RAG, agentenbasierte KI",
    level: "gefordert",
    how:
      "Fragen an freigegebene Dokumente: strukturbewusstes Chunking, Vektorsuche nur im eigenen " +
      "Wohnbereich, Antworten nur mit geprüften Quellenzitaten. Dazu ein Agent mit Function " +
      "Calling und eigenem Token (Token Exchange): Er liest mit den Rechten der Pflegekraft und " +
      "schlägt Wiedervorlagen vor, gespeichert wird erst, wenn sie bestätigt.",
    appHref: "/fragen",
    appLabel: "Fragen und Agent",
    repoPaths: [
      "apps/api/app/rag/",
      "apps/api/app/agent/",
      "supabase/migrations/20261031000000_f08_agent_rights.sql",
    ],
    status: "live",
  },
  {
    id: "security-oidc",
    text: "IT-/API-Sicherheit, OAuth 2.0/OIDC",
    level: "gefordert",
    how:
      "Login über OpenID Connect (Zitadel), Tokens nur im Server, Zugriff im Namen des Nutzers; " +
      "Row Level Security trennt die Wohnbereiche in der Datenbank selbst.",
    appHref: "/bewohner",
    appLabel: "Bewohner (nach Rollenwahl)",
    repoPaths: ["apps/api/app/auth/", "apps/web/src/lib/auth/", "supabase/migrations/"],
    status: "live",
  },
  {
    id: "local-models",
    text: "Lokale Modelle",
    level: "wuenschenswert",
    how:
      "Komplett lokaler Betrieb mit `make up-local`: Ollama (Chat und Embeddings), Docling (OCR) " +
      "und Keycloak, ohne Cloud-Dienst; nur per Konfiguration umgeschaltet.",
    repoPaths: ["apps/api/app/providers/llm/ollama.py", "apps/api/app/providers/embeddings/ollama.py", "infra/local-stack.sh"],
    status: "live",
  },
  {
    id: "docker-cicd",
    text: "Docker, CI/CD",
    level: "wuenschenswert",
    how:
      "Docker-Images für Web und API, lokaler Betrieb mit `make up`; GitHub Actions für Tests, " +
      "nächtlichen Reset und Keep-alive der Datenbank.",
    repoPaths: ["apps/api/Dockerfile", "apps/web/Dockerfile", "infra/local-stack.sh", ".github/workflows/"],
    status: "live",
  },
  {
    id: "llm-security",
    text: "Sicherheitsrisiken von LLM-Anwendungen",
    level: "wuenschenswert",
    how:
      "Bedrohungsmodell nach OWASP LLM Top 10; Schutz vor Prompt-Injection in fünf Schichten: versteckte " +
      "Schrift im PDF, Regeln, Prüfmodell, Dokumente nur als markierte Daten, Ausgabe prüfen. " +
      "Kein Modell außer der OCR sieht Bewohnernamen (Pseudonymisierung).",
    appHref: "/posteingang",
    appLabel: "Posteingang (Musterdokumente mit Angriff)",
    repoPaths: [
      "docs/security/threat-model.md",
      "apps/api/app/security/",
      "apps/api/app/privacy/",
      "apps/api/tests/security/",
    ],
    status: "live",
    showsSecurityReport: true,
  },
];
