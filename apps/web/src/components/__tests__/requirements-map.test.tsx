// F09-AC1, AC3, AC4: the project card on top, then one entry per requirement with its level,
// how it is met, a link into the app (or "in Arbeit (Stufe 2)") and links into the repo.
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ProjectCard } from "@/components/project-card";
import { RequirementsMap, SecurityReportLink } from "@/components/requirements-map";
import { REQUIREMENTS } from "@/content/requirements-map";

describe("RequirementsMap", () => {
  it("shows every requirement with its level and how it is met", () => {
    render(<RequirementsMap />);
    const entries = screen.getAllByRole("listitem").filter((li) => li.dataset.requirement);
    expect(entries).toHaveLength(REQUIREMENTS.length);
    const llm = screen.getByTestId("requirement-llm-apis");
    expect(within(llm).getByRole("heading", { name: "Anbindung von LLMs über APIs" })).toBeInTheDocument();
    expect(llm).toHaveTextContent("gefordert");
    expect(llm).toHaveTextContent("Mistral OCR");
    expect(screen.getByTestId("requirement-docker-cicd")).toHaveTextContent("wünschenswert");
  });

  it("links into the app where the requirement can be seen", () => {
    render(<RequirementsMap />);
    const rag = screen.getByTestId("requirement-rag-agents");
    expect(within(rag).getByRole("link", { name: "In der App: Fragen und Agent" })).toHaveAttribute("href", "/fragen");
  });

  it("shows the agent as done, with its code (F08)", () => {
    render(<RequirementsMap />);
    const rag = screen.getByTestId("requirement-rag-agents");
    expect(rag).not.toHaveTextContent("in Arbeit");
    expect(rag).toHaveTextContent("bestätigt");
    expect(within(rag).getByRole("link", { name: "apps/api/app/agent/" })).toBeInTheDocument();
  });

  it("links into the repository on GitHub", () => {
    render(<RequirementsMap />);
    const docker = screen.getByTestId("requirement-docker-cicd");
    const link = within(docker).getByRole("link", { name: "infra/local-stack.sh" });
    expect(link.getAttribute("href")).toMatch(/\/blob\/main\/infra\/local-stack\.sh$/);
    expect(link).toHaveAttribute("target", "_blank");
  });

  it("says 'in Arbeit (Stufe 2)' instead of an app link for what is still to come", () => {
    const local = REQUIREMENTS.find((r) => r.id === "local-models")!;
    render(<RequirementsMap entries={[{ ...local, status: "stufe2", appHref: "/fragen", appLabel: "Fragen" }]} />);
    const entry = screen.getByTestId("requirement-local-models");
    expect(entry).toHaveTextContent("in Arbeit (Stufe 2)");
    expect(within(entry).queryByRole("link", { name: /In der App/ })).not.toBeInTheDocument();
  });

  it("shows local operation as done, with the command to start it (F12)", () => {
    render(<RequirementsMap />);
    const local = screen.getByTestId("requirement-local-models");
    expect(local).not.toHaveTextContent("in Arbeit");
    expect(local).not.toHaveTextContent("Stufe 2");
    expect(local).toHaveTextContent("make up-local");
  });
});

describe("SecurityReportLink (F13-AC7)", () => {
  it("says 'Bericht folgt' while there is no report", () => {
    render(<SecurityReportLink report={null} />);
    expect(screen.getByText("Sicherheitsbericht: folgt")).toBeInTheDocument();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });

  it("links the report on GitHub once it is there", () => {
    render(<SecurityReportLink report="docs/security/reports/2026-11-01-injection.md" />);
    expect(screen.getByRole("link", { name: "Sicherheitsbericht" }).getAttribute("href")).toMatch(
      /\/blob\/main\/docs\/security\/reports\/2026-11-01-injection\.md$/,
    );
  });

  it("is part of the entry on the security risks of LLM applications", () => {
    render(<RequirementsMap />);
    expect(screen.getByTestId("requirement-llm-security")).toHaveTextContent("Sicherheitsbericht");
    expect(screen.getByTestId("requirement-llm-apis")).not.toHaveTextContent("Sicherheitsbericht");
  });
});

describe("ProjectCard", () => {
  it("says in one sentence what this is and links the project page", () => {
    render(<ProjectCard />);
    const card = screen.getByRole("region", { name: "Über das Projekt" });
    expect(card).toHaveTextContent("Bewerbungsdemo");
    expect(within(card).getByRole("link", { name: /Mehr über das Projekt/ })).toHaveAttribute("href", "/projekt");
  });
});
