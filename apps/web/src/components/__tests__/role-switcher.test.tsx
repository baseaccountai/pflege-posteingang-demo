// F01-AC2 (user name with copy button, never a password), F01-AC13 (switch = POST to logout,
// then login).
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { RoleSwitcher } from "@/components/role-switcher";
import { DEMO_ROLES } from "@/lib/auth/roles";

describe("RoleSwitcher", () => {
  it("shows the user name and where the password is - never a password", () => {
    const { container } = render(<RoleSwitcher />);
    for (const role of Object.values(DEMO_ROLES)) {
      const card = screen.getByRole("group", { name: role.label });
      expect(within(card).getByText(role.username)).toBeInTheDocument();
      expect(card).toHaveTextContent("Passwort: steht in der Bewerbung (lokal: README)");
      expect(within(card).queryByRole("button", { name: "Passwort kopieren" })).toBeNull();
    }
    // The old public passwords are in the git history; none may appear on the page.
    expect(container.textContent).not.toMatch(/Demo1?!/);
  });

  it("copies the user name to the clipboard", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    render(<RoleSwitcher />);
    const card = screen.getByRole("group", { name: "Pflegekraft WB2" });

    fireEvent.click(within(card).getByRole("button", { name: "Benutzername kopieren" }));
    expect(writeText).toHaveBeenLastCalledWith("pflege-wb2");
    // Waits for the text, not only for the button (the state update comes after the copy).
    await waitFor(() =>
      expect(within(card).getByRole("button", { name: "Benutzername kopieren" })).toHaveTextContent("Kopiert"),
    );
  });

  it("switches roles with a form POST to logout that continues to the new login", () => {
    render(<RoleSwitcher />);
    const card = screen.getByRole("group", { name: "Pflegedienstleitung" });
    const button = within(card).getByRole("button", { name: "Als Pflegedienstleitung anmelden" });
    const form = button.closest("form")!;
    expect(form.method).toBe("post");
    const action = new URL(form.action);
    expect(action.pathname).toBe("/auth/logout");
    expect(action.searchParams.get("next")).toBe("/auth/login?role=pdl");
  });
});
