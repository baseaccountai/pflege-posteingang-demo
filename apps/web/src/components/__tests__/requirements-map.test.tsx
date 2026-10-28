// F09-AC1, AC3, AC4: the project card on top, then one entry per requirement with its level,
// how it is met, a link into the app (or "in Arbeit (Stufe 2)") and links into the repo.
import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ProjectCard } from "@/components/project-card";
import { RequirementsMap } from "@/components/requirements-map";
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
    expect(within(rag).getByRole("link", { name: "In der App: Fragen" })).toHaveAttribute("href", "/fragen");
  });

  it("links into the repository on GitHub", () => {
    render(<RequirementsMap />);
    const docker = screen.getByTestId("requirement-docker-cicd");
    const link = within(docker).getByRole("link", { name: "infra/local-stack.sh" });
    expect(link.getAttribute("href")).toMatch(/\/blob\/main\/infra\/local-stack\.sh$/);
    expect(link).toHaveAttribute("target", "_blank");
  });

  it("says 'in Arbeit (Stufe 2)' instead of an app link for what is still to come", () => {
    render(<RequirementsMap />);
    const local = screen.getByTestId("requirement-local-models");
    expect(local).toHaveTextContent("in Arbeit (Stufe 2)");
    expect(within(local).queryByRole("link", { name: /In der App/ })).not.toBeInTheDocument();
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
