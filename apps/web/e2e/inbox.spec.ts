// F02-AC1 to AC7, AC12, AC13: inbox with upload, live status and messages (fake OCR).
import { expect, test } from "@playwright/test";

import { admin, loginAs, uniqueUser } from "./support/auth";
import { row, sample, upload } from "./support/inbox";
import { jpegSize } from "./support/jpeg";

const UNREADABLE = "Dokument nicht lesbar – bitte neu fotografieren (gerade, hell, ganze Seite)";

test.beforeEach(async ({ page }) => {
  await loginAs(page, "wb1", uniqueUser(), ["nurse_wb1"]);
  await page.goto("/posteingang");
});

test("shows the notice and both ways to upload (AC1, AC2)", async ({ page }) => {
  await expect(page.getByText("Bitte keine echten Personendaten hochladen.")).toBeVisible();
  await expect(page.getByLabel("Foto aufnehmen")).toHaveAttribute("capture", "environment");
  await expect(page.getByLabel("Datei hochladen")).toHaveAttribute(
    "accept",
    "image/jpeg,image/png,application/pdf",
  );
});

test("a sample letter becomes ready for review without reloading (AC5, AC6, AC13)", async ({ page }) => {
  const id = await upload(page, "Datei hochladen", sample("arztbrief_muster-bauer.pdf"));
  await expect(row(page, id)).toBeVisible();
  await expect(row(page, id)).toContainText("bereit zur Prüfung", { timeout: 15_000 });
  // The recognised type is shown before the approval (Codex review Phase 3 #7).
  await expect(row(page, id)).toContainText("Arztbrief");
  await expect(row(page, id).getByRole("link", { name: "Prüfen" })).toHaveAttribute(
    "href",
    `/posteingang/${id}`,
  );
});

test("a phone photo is made smaller in the browser before the upload (AC3)", async ({ page }) => {
  const id = await upload(page, "Foto aufnehmen", sample("arztbrief_muster-bauer_foto.jpg"));
  // What arrived on the server (Playwright does not expose multipart bodies).
  const [file] = await admin<{ content: Buffer; mime: string }[]>`
    select content, mime from public.document_files where document_id = ${id}`;
  expect(file.mime).toBe("image/jpeg");
  const size = jpegSize(Buffer.from(file.content));
  expect(size).not.toBeNull();
  expect(Math.max(size!.width, size!.height)).toBe(2000); // original: 2480 × 3508
  await expect(row(page, id)).toContainText("bereit zur Prüfung", { timeout: 15_000 });
});

for (const [file, message] of [
  ["bad/leere_seite.jpg", UNREADABLE],
  ["bad/unscharf.jpg", UNREADABLE],
  ["bad/schief.jpg", UNREADABLE],
  ["bad/kochrezept.pdf", "Kein Pflegedokument erkannt"],
]) {
  test(`${file} gets the right message (AC7)`, async ({ page }) => {
    const input = file.endsWith(".pdf") ? "Datei hochladen" : "Foto aufnehmen";
    const id = await upload(page, input, sample(file));
    await expect(row(page, id)).toContainText("nicht lesbar", { timeout: 15_000 });
    await expect(row(page, id)).toContainText(message);
    await expect(row(page, id).getByRole("link", { name: "Prüfen" })).toHaveCount(0);
  });
}

test("another file type is rejected with the reason (AC4)", async ({ page }) => {
  await expect(page.getByLabel("Datei hochladen")).toBeEnabled();
  await page.getByLabel("Datei hochladen").setInputFiles({
    name: "notiz.pdf",
    mimeType: "application/pdf",
    buffer: Buffer.from("Das ist eigentlich nur Text."),
  });
  // Next.js has its own (empty) role=alert for route announcements, hence the text filter.
  await expect(
    page.getByRole("alert").filter({ hasText: "Nur JPEG, PNG oder PDF sind erlaubt." }),
  ).toBeVisible();
});

test("WB2 does not see the WB1 document (AC13)", async ({ page, browser }) => {
  const id = await upload(page, "Datei hochladen", sample("medikationsplan_muster-bauer.pdf"));
  const other = await browser.newPage();
  await loginAs(other, "wb2", uniqueUser("pflege-wb2"), ["nurse_wb2"]);
  await other.goto("/posteingang");
  await expect(other.getByRole("heading", { name: "Posteingang" })).toBeVisible();
  await expect(other.getByTestId(`document-${id}`)).toHaveCount(0);
  const listed = await other.request.get("/api/documents");
  expect(listed.headers()["cache-control"]).toContain("no-store");
  expect((await listed.json()).map((d: { id: string }) => d.id)).not.toContain(id);
  await other.close();
});

test("the PDL uploads into the ward she chooses (AC12)", async ({ browser }) => {
  const pdl = await browser.newPage();
  await loginAs(pdl, "pdl", uniqueUser("pdl"), ["pdl"]);
  await pdl.goto("/posteingang");
  await expect(pdl.getByLabel("Datei hochladen")).toBeEnabled();
  await pdl.getByLabel("Wohnbereich").selectOption("wb2");
  const id = await upload(pdl, "Datei hochladen", sample("ueberleitungsbogen_testfeld.pdf"));
  await expect(row(pdl, id)).toContainText("WB2");
  await pdl.close();
});
