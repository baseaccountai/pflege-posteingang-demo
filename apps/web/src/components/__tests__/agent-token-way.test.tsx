// F08-AC2: /projekt says openly how the agent gets its token - including the weaker fallback.
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AgentTokenWay } from "@/components/agent-token-way";

describe("AgentTokenWay", () => {
  it("names the token exchange at the identity provider", () => {
    render(<AgentTokenWay way="exchange" />);
    expect(screen.getByTestId("agent-token-way")).toHaveTextContent("Token Exchange (RFC 8693) bei Zitadel");
  });

  it("names the fallback openly", () => {
    render(<AgentTokenWay way="self_signed" />);
    expect(screen.getByTestId("agent-token-way")).toHaveTextContent("Rückfall: Die API stellt das Agenten-Token selbst aus");
  });

  it("says when there is no agent or the API does not answer", () => {
    const { rerender } = render(<AgentTokenWay way="off" />);
    expect(screen.getByTestId("agent-token-way")).toHaveTextContent("Der Agent ist zurzeit nicht eingerichtet.");
    rerender(<AgentTokenWay way={null} />);
    expect(screen.getByTestId("agent-token-way")).toHaveTextContent("gerade nicht abrufbar");
  });
});
