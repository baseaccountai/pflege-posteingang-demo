// F02-AC6, AC8, AC13: inbox rows, live status without reload, retry.
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { InboxList, type InboxDocument } from "@/components/inbox-list";

const doc = (over: Partial<InboxDocument>): InboxDocument => ({
  id: "d1",
  ward_id: "wb1",
  doc_type: null,
  status: "uploaded",
  error_code: null,
  created_at: "2026-10-27T09:05:00Z",
  ...over,
});

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

beforeEach(() => vi.useFakeTimers());
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("InboxList", () => {
  it("marks a document with findings of the injection check as suspicious (F07-AC6)", () => {
    render(
      <InboxList
        documents={[
          doc({ id: "a", status: "ready_for_review", screening_result: "suspicious" }),
          doc({ id: "b", status: "ready_for_review", screening_result: "clean" }),
        ]}
        onChange={vi.fn()}
      />,
    );
    expect(screen.getByTestId("document-a")).toHaveTextContent("verdächtig");
    expect(screen.getByTestId("document-b")).not.toHaveTextContent("verdächtig");
  });

  it("shows badge, type, time, message and the review link", () => {
    render(
      <InboxList
        documents={[
          doc({ id: "a", status: "ready_for_review", doc_type: "arztbrief" }),
          doc({ id: "b", status: "unreadable", error_code: "not_care_document" }),
        ]}
        onChange={vi.fn()}
      />,
    );
    const ready = screen.getByTestId("document-a");
    expect(ready).toHaveTextContent("bereit zur Prüfung");
    expect(ready).toHaveTextContent("Arztbrief");
    expect(within(ready).getByRole("link", { name: "Prüfen" })).toHaveAttribute("href", "/posteingang/a");
    expect(screen.getByTestId("document-b")).toHaveTextContent("Kein Pflegedokument erkannt");
    expect(within(screen.getByTestId("document-b")).queryByRole("link")).toBeNull();
  });

  it("polls every 3 seconds while something is running and stops afterwards", async () => {
    const fetch = vi.fn().mockResolvedValue(jsonResponse([doc({ status: "ready_for_review" })]));
    vi.stubGlobal("fetch", fetch);
    const onChange = vi.fn();
    const { rerender } = render(<InboxList documents={[doc({ status: "processing" })]} onChange={onChange} />);

    await act(() => vi.advanceTimersByTimeAsync(3000));
    expect(fetch).toHaveBeenCalledWith("/api/documents", expect.objectContaining({ cache: "no-store" }));
    expect(onChange).toHaveBeenCalledWith([doc({ status: "ready_for_review" })]);

    rerender(<InboxList documents={[doc({ status: "ready_for_review" })]} onChange={onChange} />);
    fetch.mockClear();
    await act(() => vi.advanceTimersByTimeAsync(9000));
    expect(fetch).not.toHaveBeenCalled();
  });

  it("offers a retry for failed documents", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ id: "d1", status: "failed" }, 202))
      .mockResolvedValue(jsonResponse([doc({ status: "processing" })]));
    vi.stubGlobal("fetch", fetch);
    const onChange = vi.fn();
    render(<InboxList documents={[doc({ status: "failed", error_code: "ocr_unavailable" })]} onChange={onChange} />);

    fireEvent.click(screen.getByRole("button", { name: "Erneut versuchen" }));
    await act(() => vi.advanceTimersByTimeAsync(0));
    expect(fetch.mock.calls[0][0]).toBe("/api/documents/d1/retry");
    expect(fetch.mock.calls[0][1].method).toBe("POST");
    expect(onChange).toHaveBeenCalledWith([doc({ status: "processing" })]);
  });

  it("says so when the inbox is empty", () => {
    render(<InboxList documents={[]} onChange={vi.fn()} />);
    expect(screen.getByText("Noch keine Dokumente.")).toBeInTheDocument();
  });
});
