// F05-AC5, AC8, AC10, AC11, AC12: questions with a resident filter, answers with sources and
// the model, history only in this page's memory.
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { QuestionChat } from "@/components/question-chat";

vi.mock("@/lib/navigation", () => ({ goTo: vi.fn(), leaveEndedSession: vi.fn() }));
import { leaveEndedSession } from "@/lib/navigation";

const RESIDENTS = [
  { id: "r1", display_name: "Hr. Muster-Bauer" },
  { id: "r2", display_name: "Fr. Beispiel" },
];
const ANSWER = {
  answer: "Ramipril 5 mg morgens [Q1].",
  sources: [{ document_id: "d1", doc_type: "arztbrief", document_date: "2026-10-20", resident_name: "Hr. Muster-Bauer", page: 2 }],
  model: "mistral-small-latest",
  no_hits: false,
  sent_to_model: {
    question: "Wie ist Ramipril bei Bewohner_K42 dosiert?",
    sources: [{ n: 1, text: "## Medikation\nBewohner_K42: Ramipril 5 mg morgens" }],
  },
};

function json(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

function ask(text: string) {
  fireEvent.change(screen.getByLabelText("Frage"), { target: { value: text } });
  fireEvent.click(screen.getByRole("button", { name: "Fragen" }));
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

describe("QuestionChat", () => {
  it("shows the answer with the model and its sources linked to the original", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json(ANSWER)));
    render(<QuestionChat residents={RESIDENTS} initialResident="" />);
    ask("Wie ist Ramipril dosiert?");
    const answer = await screen.findByTestId("answer-0");
    expect(answer).toHaveTextContent("Wie ist Ramipril dosiert?");
    expect(answer).toHaveTextContent("Ramipril 5 mg morgens [Q1].");
    expect(answer).toHaveTextContent("Antwort von Mistral Small");
    const source = within(answer).getByRole("link", { name: /Arztbrief vom 20.10.2026 · Hr. Muster-Bauer · Seite 2/ });
    expect(source).toHaveAttribute("href", "/api/documents/d1/file");
    expect(source).toHaveAttribute("target", "_blank");
  });

  it("shows on request exactly what the model saw, with placeholders (F06-AC7)", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json(ANSWER)));
    render(<QuestionChat residents={RESIDENTS} initialResident="" />);
    ask("Wie ist Ramipril bei Hr. Muster-Bauer dosiert?");
    const answer = await screen.findByTestId("answer-0");
    const seen = within(answer).getByText("Das hat das KI-Modell gesehen").closest("details")!;
    expect(seen).not.toHaveAttribute("open");
    expect(seen).toHaveTextContent("Frage: Wie ist Ramipril bei Bewohner_K42 dosiert?");
    expect(seen).toHaveTextContent("[Q1] ## Medikation Bewohner_K42: Ramipril 5 mg morgens");
    expect(seen).not.toHaveTextContent("Muster-Bauer");
  });

  it("has no such section when no model was asked", async () => {
    const noHits = { answer: "Keine Treffer in deinem Wohnbereich.", sources: [], model: "m", no_hits: true, sent_to_model: null };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json(noHits)));
    render(<QuestionChat residents={RESIDENTS} initialResident="" />);
    ask("Wer ist Hr. Niemand?");
    const answer = await screen.findByTestId("answer-0");
    expect(within(answer).queryByText("Das hat das KI-Modell gesehen")).not.toBeInTheDocument();
  });

  it("sends the chosen resident, preselected from the record link", async () => {
    const fetch = vi.fn().mockResolvedValue(json(ANSWER));
    vi.stubGlobal("fetch", fetch);
    render(<QuestionChat residents={RESIDENTS} initialResident="r2" />);
    expect(screen.getByLabelText("Bewohner")).toHaveValue("r2");
    ask("Was steht im Arztbrief?");
    await waitFor(() => expect(fetch).toHaveBeenCalled());
    const [url, init] = fetch.mock.calls[0];
    expect(url).toBe("/api/questions");
    expect(JSON.parse(init.body)).toEqual({ question: "Was steht im Arztbrief?", resident_id: "r2" });
  });

  it("asks across all own residents without a filter", async () => {
    const fetch = vi.fn().mockResolvedValue(json(ANSWER));
    vi.stubGlobal("fetch", fetch);
    render(<QuestionChat residents={RESIDENTS} initialResident="" />);
    expect(screen.getByLabelText("Bewohner")).toHaveValue("");
    ask("Wer bekommt Ramipril?");
    await waitFor(() => expect(fetch).toHaveBeenCalled());
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ question: "Wer bekommt Ramipril?" });
  });

  it("shows no hits without sources", async () => {
    const noHits = { answer: "Keine Treffer in deinem Wohnbereich.", sources: [], model: "mistral-small-latest", no_hits: true };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json(noHits)));
    render(<QuestionChat residents={RESIDENTS} initialResident="" />);
    ask("Wie geht es Hr. Niemand?");
    const answer = await screen.findByTestId("answer-0");
    expect(answer).toHaveTextContent("Keine Treffer in deinem Wohnbereich.");
    expect(within(answer).queryByRole("link")).not.toBeInTheDocument();
  });

  it("explains a used-up daily quota", async () => {
    const quota = { error_code: "daily_quota", message: "Tageskontingent der Demo erreicht – Musterdaten bleiben ansehbar, morgen geht es weiter." };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json(quota, 429)));
    render(<QuestionChat residents={RESIDENTS} initialResident="" />);
    ask("Wie ist Ramipril dosiert?");
    expect(await screen.findByText(quota.message)).toBeInTheDocument();
  });

  it("leaves an ended session", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(json({}, 401)));
    render(<QuestionChat residents={RESIDENTS} initialResident="" />);
    ask("Wie ist Ramipril dosiert?");
    await waitFor(() => expect(leaveEndedSession).toHaveBeenCalled());
    expect(screen.queryByTestId("answer-0")).not.toBeInTheDocument();
  });

  it("takes at most 500 characters and no empty question", () => {
    render(<QuestionChat residents={RESIDENTS} initialResident="" />);
    const field = screen.getByLabelText("Frage");
    expect(field).toHaveAttribute("maxLength", "500");
    expect(screen.getByRole("button", { name: "Fragen" })).toBeDisabled();
    fireEvent.change(field, { target: { value: "x".repeat(20) } });
    expect(screen.getByText("20/500")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Fragen" })).toBeEnabled();
  });

  it("keeps the conversation only in the page, never in the browser storage", async () => {
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    vi.stubGlobal("fetch", vi.fn().mockImplementation(async () => json(ANSWER)));
    render(<QuestionChat residents={RESIDENTS} initialResident="" />);
    ask("Erste Frage?");
    await screen.findByTestId("answer-0");
    ask("Zweite Frage?");
    await screen.findByTestId("answer-1");
    expect(screen.getByTestId("answer-0")).toHaveTextContent("Erste Frage?");
    expect(setItem).not.toHaveBeenCalled();
  });
});
