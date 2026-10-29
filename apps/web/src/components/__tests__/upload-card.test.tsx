// F02-AC1, AC2, AC4, AC12: upload card with camera and file input, fixed notice, PDL ward.
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { UploadCard } from "@/components/upload-card";

vi.mock("@/lib/image/downscale", () => ({
  prepareUpload: vi.fn(async () => new File(["small"], "foto.jpg", { type: "image/jpeg" })),
}));

afterEach(() => vi.unstubAllGlobals());

function jsonResponse(status: number, body: unknown) {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

describe("UploadCard", () => {
  it("always shows the exact notice above the upload", () => {
    render(<UploadCard onUploaded={vi.fn()} />);
    expect(screen.getByText("Bitte keine echten Personendaten hochladen.")).toBeInTheDocument();
  });

  it("says which provider sees the original (F06-AC9, AC12)", () => {
    render(<UploadCard onUploaded={() => {}} />);
    expect(screen.getByTestId("privacy-notice")).toHaveTextContent(
      "Die Texterkennung (OCR) läuft öffentlich bei Mistral und sieht das Original; alle weiteren KI-Schritte sehen nur Platzhalter. Im lokalen Betrieb verlässt nichts den Rechner.",
    );
    expect(screen.getByTestId("privacy-notice")).toHaveTextContent("Namen ohne Anrede oder Titel");
  });

  it("offers the back camera and a file upload for JPEG, PNG and PDF", () => {
    render(<UploadCard onUploaded={vi.fn()} />);
    const camera = screen.getByLabelText("Foto aufnehmen");
    expect(camera).toHaveAttribute("capture", "environment");
    expect(camera).toHaveAttribute("accept", "image/jpeg,image/png");
    const file = screen.getByLabelText("Datei hochladen");
    expect(file).toHaveAttribute("accept", "image/jpeg,image/png,application/pdf");
    expect(file).not.toHaveAttribute("capture");
  });

  it("uploads the prepared file and reports the new document", async () => {
    const fetch = vi.fn().mockResolvedValue(jsonResponse(202, { id: "d1", status: "uploaded" }));
    vi.stubGlobal("fetch", fetch);
    const onUploaded = vi.fn();
    render(<UploadCard onUploaded={onUploaded} />);

    const photo = new File(["big"], "IMG_1.jpg", { type: "image/jpeg" });
    fireEvent.change(screen.getByLabelText("Foto aufnehmen"), { target: { files: [photo] } });

    await waitFor(() => expect(onUploaded).toHaveBeenCalledWith({ id: "d1", status: "uploaded" }));
    const [url, init] = fetch.mock.calls[0];
    expect(url).toBe("/api/documents");
    expect(init.method).toBe("POST");
    const sent = (init.body as FormData).get("file") as File;
    expect(sent.name).toBe("foto.jpg"); // the downscaled version, not the original
    expect((init.body as FormData).get("ward_id")).toBeNull();
  });

  it("shows the server's reason when the file is rejected", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(415, { error_code: "unsupported_type", message: "Nur JPEG, PNG oder PDF sind erlaubt." }),
      ),
    );
    const onUploaded = vi.fn();
    render(<UploadCard onUploaded={onUploaded} />);
    fireEvent.change(screen.getByLabelText("Datei hochladen"), {
      target: { files: [new File(["x"], "a.pdf", { type: "application/pdf" })] },
    });
    expect(await screen.findByRole("alert")).toHaveTextContent("Nur JPEG, PNG oder PDF sind erlaubt.");
    expect(onUploaded).not.toHaveBeenCalled();
  });

  it("lets the PDL choose the ward and sends it along", async () => {
    const fetch = vi.fn().mockResolvedValue(jsonResponse(202, { id: "d2", status: "uploaded" }));
    vi.stubGlobal("fetch", fetch);
    render(<UploadCard onUploaded={vi.fn()} wards={["wb1", "wb2"]} />);
    fireEvent.change(screen.getByLabelText("Wohnbereich"), { target: { value: "wb2" } });
    fireEvent.change(screen.getByLabelText("Datei hochladen"), {
      target: { files: [new File(["%PDF"], "a.pdf", { type: "application/pdf" })] },
    });
    await waitFor(() => expect(fetch).toHaveBeenCalled());
    expect((fetch.mock.calls[0][1].body as FormData).get("ward_id")).toBe("wb2");
  });

  it("has no ward choice for a nurse", () => {
    render(<UploadCard onUploaded={vi.fn()} />);
    expect(screen.queryByLabelText("Wohnbereich")).toBeNull();
  });
});
