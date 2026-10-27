import path from "node:path";
import { expect, type Page } from "@playwright/test";

import { SAMPLES_DIR } from "./env";

export const sample = (name: string) => path.join(SAMPLES_DIR, name);

/** Chooses a file in one of the two inputs and returns the new document's id. */
export async function upload(page: Page, input: "Foto aufnehmen" | "Datei hochladen", file: string) {
  const answer = page.waitForResponse(
    (r) => r.url().endsWith("/api/documents") && r.request().method() === "POST",
  );
  await expect(page.getByLabel(input)).toBeEnabled(); // React has taken over the page
  await page.getByLabel(input).setInputFiles(file);
  const response = await answer;
  expect(response.status()).toBe(202);
  return (await response.json()).id as string;
}

export const row = (page: Page, id: string) => page.getByTestId(`document-${id}`);
