// F04-AC1 to AC10: resident list per role, record with provenance, "Fragen zu diesem
// Bewohner", follow-up done, foreign ids. Data per test: a fresh resident of its own.
import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";

import { admin, loginAs, uniqueUser } from "./support/auth";
import { WB1_RESIDENT, WB2_RESIDENT } from "./support/env";

const DOSE = { morgens: "1", mittags: "0", abends: "1", nachts: "0" };

/** A WB1 resident with a small record: approved plan, medications, diagnosis, follow-ups. */
async function residentWithRecord() {
  const id = randomUUID();
  const name = `Fr. Akte-${id.slice(0, 6)}`;
  await admin`insert into public.residents (id, ward_id, display_name, room)
              values (${id}, 'wb1', ${name}, '107')`;
  const [{ doc }] = await admin<{ doc: string }[]>`
    insert into public.documents (ward_id, resident_id, uploaded_by, upload_session, status,
      doc_type, document_date, approved_by, approved_by_name, approved_at)
    values ('wb1', ${id}, 'seed', 'seed', 'approved', 'medikationsplan', '2026-10-22',
      'seed', 'Pflegekraft WB1', now() - interval '1 day')
    returning id::text as doc`;
  const medication = async (name: string, status: string) => {
    const [{ med }] = await admin<{ med: string }[]>`
      insert into public.medications (ward_id, resident_id, name, strength, dosage, status, created_by)
      values ('wb1', ${id}, ${name}, '5 mg', ${admin.json(DOSE)}, ${status}, 'seed')
      returning id::text as med`;
    return med;
  };
  const event = (med: string, kind: string, actor = "human") => admin`
    insert into public.medication_events (ward_id, medication_id, kind, document_id, after,
      actor_type, created_by, confirmed_by, confirmed_by_name)
    values ('wb1', ${med}, ${kind}, ${doc}, ${admin.json({ name: "x", strength: "5 mg", dosage: DOSE })},
      ${actor}, 'seed', 'seed', 'Pflegekraft WB1')`;
  await event(await medication("Ramipril", "active"), "new");
  await event(await medication("Torasemid", "active"), "new", "agent");
  await event(await medication("Simvastatin", "discontinued"), "discontinued");
  await admin`
    insert into public.diagnoses (ward_id, resident_id, text, source_document_id, actor_type,
      created_by, confirmed_by, confirmed_by_name)
    values ('wb1', ${id}, 'Herzinsuffizienz', ${doc}, 'human', 'seed', 'seed', 'Pflegekraft WB1')`;
  for (const [title, days] of [
    ["Blutdruck kontrollieren", -1],
    ["Arzttermin vereinbaren", 5],
  ] as const) {
    await admin`
      insert into public.follow_ups (ward_id, resident_id, title, due_date, source_document_id,
        actor_type, created_by, confirmed_by, confirmed_by_name)
      values ('wb1', ${id}, ${title}, (now() at time zone 'Europe/Berlin')::date + ${days}::int,
        ${doc}, 'human', 'seed', 'seed', 'Pflegekraft WB1')`;
  }
  return { id, name };
}

test("list shows Neu, follow-ups and due ones for the own ward (AC1, AC2)", async ({ page }) => {
  const resident = await residentWithRecord();
  await loginAs(page, "wb1", uniqueUser(), ["nurse_wb1"]);
  await page.goto("/bewohner");
  const row = page.getByTestId(`resident-${resident.id}`);
  await expect(row).toContainText("Zimmer 107 · WB 1");
  await expect(row.getByText("Neu", { exact: true })).toBeVisible();
  await expect(row).toContainText("2 Wiedervorlagen");
  await expect(row.getByText("1 fällig")).toBeVisible();
  await expect(page.locator("body")).not.toContainText(WB2_RESIDENT.name);
});

test("PDL sees the residents grouped by ward (AC1)", async ({ page }) => {
  await loginAs(page, "pdl", uniqueUser("pdl"), ["pdl"]);
  await page.goto("/bewohner");
  await expect(page.getByRole("region", { name: "WB 1" }).getByRole("link", { name: WB1_RESIDENT.name })).toBeVisible();
  await expect(page.getByRole("region", { name: "WB 2" }).getByRole("link", { name: WB2_RESIDENT.name })).toBeVisible();
});

test("record shows every section with provenance (AC3 to AC6, AC10)", async ({ page }) => {
  const resident = await residentWithRecord();
  await loginAs(page, "wb1", uniqueUser(), ["nurse_wb1"]);
  const response = await page.goto(`/bewohner/${resident.id}`);
  expect(response?.headers()["cache-control"]).toContain("no-store");
  await expect(page.getByRole("heading", { name: resident.name })).toBeVisible();
  for (const section of ["Medikation", "Diagnosen", "Wiedervorlagen", "Dokumente"]) {
    await expect(page.getByRole("region", { name: section })).toBeVisible();
  }
  const meds = page.getByRole("region", { name: "Medikation" });
  await expect(meds).toContainText("Ramipril 5 mg");
  await expect(meds).toContainText("1-0-1-0");
  await expect(meds).toContainText("Medikationsplan vom 22.10.2026 · freigegeben von Pflegekraft WB1");
  await expect(meds).toContainText("vom Agenten angelegt · bestätigt von Pflegekraft WB1");
  await expect(meds.locator("s", { hasText: "Simvastatin" })).toBeVisible();
  await expect(meds).toContainText("laut Medikationsplan vom 22.10.2026");
  await expect(page.getByRole("region", { name: "Diagnosen" })).toContainText(
    "Herzinsuffizienz",
  );
  await expect(page.getByRole("region", { name: "Diagnosen" })).toContainText("Medikationsplan vom 22.10.2026");
  const docs = page.getByRole("region", { name: "Dokumente" });
  await expect(docs.getByRole("link", { name: "Medikationsplan vom 22.10.2026" })).toHaveAttribute(
    "target",
    "_blank",
  );
});

test("Fragen zu diesem Bewohner opens the questions with this resident (AC7)", async ({ page }) => {
  await loginAs(page, "wb1", uniqueUser(), ["nurse_wb1"]);
  await page.goto(`/bewohner/${WB1_RESIDENT.id}`);
  await page.getByRole("link", { name: "Fragen zu diesem Bewohner" }).click();
  await page.waitForURL(`/fragen?bewohner=${WB1_RESIDENT.id}`);
});

test("a follow-up is marked done with who and when (AC8)", async ({ page }) => {
  const resident = await residentWithRecord();
  await loginAs(page, "wb1", uniqueUser(), ["nurse_wb1"]);
  await page.goto(`/bewohner/${resident.id}`);
  await page.getByRole("button", { name: "Blutdruck kontrollieren als erledigt markieren" }).click();
  await expect(page.getByRole("region", { name: "Wiedervorlagen" })).toContainText(
    "erledigt von Pflegekraft WB1",
  );
  await page.goto("/bewohner");
  const row = page.getByTestId(`resident-${resident.id}`);
  await expect(row).toContainText("1 Wiedervorlage");
  await expect(row).not.toContainText("fällig");
});

test("foreign, unknown and malformed ids give screen 8 (AC9)", async ({ page }) => {
  const resident = await residentWithRecord();
  await loginAs(page, "wb2", uniqueUser("pflege-wb2"), ["nurse_wb2"]);
  for (const id of [resident.id, randomUUID(), "kein-uuid"]) {
    await page.goto(`/bewohner/${id}`);
    await expect(page.getByRole("heading", { name: "Nicht gefunden oder kein Zugriff" })).toBeVisible();
    await expect(page.locator("body")).not.toContainText(resident.name);
    await expect(page.locator("body")).not.toContainText("Ramipril");
  }
});
