import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AppContentShell } from "./AppContentShell";
import { useAuth } from "@/context/AuthContext";

vi.mock("@/context/AuthContext", () => ({
  useAuth: vi.fn(),
}));

describe("AppContentShell", () => {
  // coridian_, 2026-10-19, screenshot: "still weird clipping and scaling on
  // the desktop welcome page" — DesktopSidebar already renders nothing for
  // a signed-out visitor, but the content wrapper used to reserve md:pl-60
  // of space for it regardless, leaving a large empty gap instead of a
  // centered landing page.
  it("does not reserve sidebar space when signed out", () => {
    vi.mocked(useAuth).mockReturnValue({ session: null } as ReturnType<typeof useAuth>);
    render(
      <AppContentShell>
        <span>Welcome</span>
      </AppContentShell>,
    );
    const wrapper = screen.getByText("Welcome").parentElement as HTMLElement;
    expect(wrapper.className).not.toContain("pl-60");
  });

  it("reserves sidebar space when signed in, matching DesktopSidebar's own visibility", () => {
    vi.mocked(useAuth).mockReturnValue({ session: { user: { id: "u1" } } } as ReturnType<typeof useAuth>);
    render(
      <AppContentShell>
        <span>Dashboard</span>
      </AppContentShell>,
    );
    const wrapper = screen.getByText("Dashboard").parentElement as HTMLElement;
    expect(wrapper.className).toContain("md:pl-60");
  });
});
