// F10-AC16: /projekt says whether the AI provider answers - so a failed request can be told
// apart from a provider outage.
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ModelStatus } from "@/components/model-status";

describe("ModelStatus", () => {
  it("names a reachable and a disturbed provider", () => {
    const { rerender } = render(<ModelStatus status="ok" />);
    expect(screen.getByTestId("model-status")).toHaveTextContent("KI-Anbieter: erreichbar");
    rerender(<ModelStatus status="unavailable" />);
    expect(screen.getByTestId("model-status")).toHaveTextContent("KI-Anbieter: gestört");
  });

  it("says when the API itself does not answer", () => {
    render(<ModelStatus status={null} />);
    expect(screen.getByTestId("model-status")).toHaveTextContent("KI-Anbieter: Zustand gerade nicht abrufbar");
  });
});
