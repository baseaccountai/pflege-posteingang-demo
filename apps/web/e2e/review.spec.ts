// F03-AC4 to AC8, AC10, AC12: review a medication plan - wrong resident suggested, choose
// another, confirmation resets, comparison recomputed, confirm, approve (fake OCR + LLM).
import { randomUUID } from "node:crypto";
import { expect, test, type Page } from "@playwright/test";

import { admin, loginAs, uniqueUser } from "./support/auth";
import { row, sample, upload } from "./support/inbox";

const DOSE = { morgens: "1", mittags: "0", abends: "0", nachts: "0" };

/** A resident of WB1 only this test uses, with the medication record of the samples. */
async function residentWithRecord() {
  const id = randomUUID();
  const name = `Hr. Prüfung-${id.slice(0, 6)}`;
  await admin`insert into public.residents (id, ward_id, display_name) values (${id}, 'wb1', ${name})`;
  for (const [med, strength] of [
    ["Ramipril", "5 mg"],
    ["Metformin", "500 mg"],
    ["Simvastatin", "20 mg"],
  ]) {
    await admin`
      insert into public.medications (ward_id, resident_id, name, strength, dosage, created_by)
      values ('wb1', ${id}, ${med}, ${strength}, ${admin.json(DOSE)}, 'seed')`;
  }
  return { id, name };
}

async function openReview(page: Page) {
  await page.goto("/posteingang");
  const id = await upload(page, "Datei hochladen", sample("medikationsplan_muster-bauer.pdf"));
  await expect(row(page, id)).toContainText("bereit zur Prüfung", { timeout: 15_000 });
  await row(page, id).getByRole("link", { name: "Prüfen" }).click();
  await page.waitForURL(`/posteingang/${id}`);
  return id;
}

const badge = (page: Page, name: string) =>
  page.getByRole("list", { name: "Medikationsabgleich" }).getByRole("listitem").filter({ hasText: name });

test.beforeEach(async ({ page }) => {
  await loginAs(page, "wb1", uniqueUser(), ["nurse_wb1"]);
});

test("wrong resident suggested: choose another, confirm, approve (AC5 to AC8)", async ({ page }) => {
  const other = await residentWithRecord();
  const doc = await openReview(page);

  await expect(page.getByText("KI-Vorschlag – bitte jedes Feld prüfen")).toBeVisible();
  await expect(page.getByText(/Modell: fake-llm/)).toBeVisible();
  // The document names Hr. Muster-Bauer, so he is suggested - but it is the wrong one.
  const resident = page.getByLabel("Bewohner", { exact: true });
  await expect(resident.locator("option:checked")).toHaveText("Hr. Muster-Bauer");
  await page.getByLabel("Bewohner bestätigen").check();

  await resident.selectOption(other.id);
  await expect(page.getByLabel("Bewohner bestätigen")).not.toBeChecked();
  await expect(page.getByRole("button", { name: "Freigeben" })).toBeDisabled();
  // Comparison against the chosen resident's record (F03-AC7).
  await expect(badge(page, "Ramipril")).toContainText("unverändert");
  await expect(badge(page, "Metformin")).toContainText("geändert");
  await expect(badge(page, "Torasemid")).toContainText("neu");
  await expect(badge(page, "Simvastatin")).toContainText("abgesetzt");

  await page.getByLabel("Bewohner bestätigen").check();
  await page.getByRole("button", { name: "Freigeben" }).click();
  await page.waitForURL(`/bewohner/${other.id}`);
  // F04: the approved entries appear in the record with their origin; the original opens.
  const meds = page.getByRole("region", { name: "Medikation" });
  await expect(meds.getByTestId(/^medication-/).filter({ hasText: "Torasemid" })).toContainText(
    /Medikationsplan vom \d\d\.\d\d\.\d{4} · freigegeben von Pflegekraft WB1/,
  );
  const original = page.getByRole("region", { name: "Dokumente" }).getByRole("link").first();
  const file = await page.request.get((await original.getAttribute("href"))!);
  expect(file.status()).toBe(200);
  expect(file.headers()["content-type"]).toBe("application/pdf");

  const events = await admin<{ name: string; kind: string }[]>`
    select m.name, e.kind from public.medication_events e
    join public.medications m on m.id = e.medication_id
    where m.resident_id = ${other.id} and e.document_id = ${doc} order by m.name`;
  expect(events).toEqual([
    { name: "Metformin", kind: "changed" },
    { name: "Simvastatin", kind: "discontinued" },
    { name: "Torasemid", kind: "new" },
  ]);
  const [document] = await admin<{ status: string; resident_id: string }[]>`
    select status::text, resident_id::text from public.documents where id = ${doc}`;
  expect(document).toEqual({ status: "approved", resident_id: other.id });
});

test("the original is shown next to the fields (AC4)", async ({ page }) => {
  const file = page.waitForResponse((r) => r.url().includes("/file"));
  const doc = await openReview(page);
  const response = await file;
  expect(response.url()).toContain(`/api/documents/${doc}/file`);
  expect(response.headers()["content-type"]).toBe("application/pdf");
  expect(response.headers()["x-content-type-options"]).toBe("nosniff");
  await expect(page.getByTitle("Originaldokument")).toBeAttached();
});

test("rejecting a document writes nothing into the record (AC10)", async ({ page }) => {
  const doc = await openReview(page);
  await page.getByRole("button", { name: "Verwerfen" }).click();
  await page.waitForURL("/posteingang");
  await expect(row(page, doc)).toContainText("verworfen");
  const [{ count }] = await admin<{ count: number }[]>`
    select count(*)::int as count from public.medication_events where document_id = ${doc}`;
  expect(count).toBe(0);
});
