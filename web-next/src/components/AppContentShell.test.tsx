import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AppContentShell } from "./AppContentShell";
import { useAuth } from "@/context/AuthContext";

vi.mock("@/context/AuthContext", () => ({
  useAuth: vi.fn(),
}));

const navigation = vi.hoisted(() => ({ pathname: "/" as string | null }));
vi.mock("next/navigation", () => ({
  usePathname: () => navigation.pathname,
  useSearchParams: () => new URLSearchParams("name=FFLR%20Test%20League"),
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
    // Phone: clears the floating GM orb (52px + 12px offset) so it never covers the last content.
    expect(wrapper.className).toContain("pb-12");
  });

  it("shows the ESPN not-available state instead of a page ESPN leagues can't feed", () => {
    vi.mocked(useAuth).mockReturnValue({ session: { user: { id: "u1" } } } as ReturnType<typeof useAuth>);
    navigation.pathname = `/waivers/${encodeURIComponent("espn:42654852:2026")}`;
    render(
      <AppContentShell>
        <span>Waivers page</span>
      </AppContentShell>,
    );
    expect(screen.queryByText("Waivers page")).toBeNull();
    expect(screen.getByRole("heading", { name: "Not available for ESPN leagues yet." })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "My Team" })).toHaveAttribute(
      "href",
      `/my-team/${encodeURIComponent("espn:42654852:2026")}?name=FFLR%20Test%20League`,
    );
  });

  it("renders supported pages normally for ESPN leagues", () => {
    vi.mocked(useAuth).mockReturnValue({ session: { user: { id: "u1" } } } as ReturnType<typeof useAuth>);
    navigation.pathname = `/my-team/${encodeURIComponent("espn:42654852:2026")}`;
    render(
      <AppContentShell>
        <span>My Team page</span>
      </AppContentShell>,
    );
    expect(screen.getByText("My Team page")).toBeInTheDocument();
    navigation.pathname = "/";
  });
});
