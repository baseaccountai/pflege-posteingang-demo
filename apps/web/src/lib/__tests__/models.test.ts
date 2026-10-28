// F05-AC10: the answer names the model in words a nurse understands.
import { describe, expect, it } from "vitest";

import { modelLabel } from "@/lib/models";

describe("modelLabel", () => {
  it.each([
    ["mistral-small-latest", "Mistral Small"],
    ["mistral-small-2506", "Mistral Small"],
    ["qwen3:8b", "qwen3:8b (lokal)"],
    ["fake-llm (Testattrappe)", "fake-llm (Testattrappe)"],
  ])("%s -> %s", (model, label) => {
    expect(modelLabel(model)).toBe(label);
  });
});
