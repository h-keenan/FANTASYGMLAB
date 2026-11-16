import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AppShellBar } from "./AppShellBar";

const nav = vi.hoisted(() => ({ pathname: "/dashboard/league-1", leagueId: "league-1" as string | undefined, visible: true }));
vi.mock("next/navigation", () => ({
  usePathname: () => nav.pathname,
  useParams: () => (nav.leagueId ? { leagueId: nav.leagueId } : {}),
  useSearchParams: () => new URLSearchParams("name=My%20League"),
}));
vi.mock("@/lib/useShellNav", () => ({ useShellNav: () => ({ enabled: nav.visible, barVisible: nav.visible }) }));
vi.mock("@/context/AuthContext", () => ({ useAuth: () => ({ session: { user: { id: "u1" } } }) }));
vi.mock("@/lib/useIsPro", () => ({ useIsPro: () => false }));

describe("AppShellBar", () => {
  it("renders nothing when the shell is off", () => {
    nav.visible = false;
    const { container } = render(<AppShellBar />);
    expect(container).toBeEmptyDOMElement();
    nav.visible = true;
  });

  it("is a league-aware nav: Today lit on the dashboard, links carry the league", () => {
    render(<AppShellBar />);
    const bar = screen.getByRole("navigation", { name: "League sections" });
    expect(within(bar).getByRole("link", { name: "Today" })).toHaveAttribute("aria-current", "page");
    expect(within(bar).getByRole("link", { name: "Trades" })).toHaveAttribute("href", "/trade-hub/league-1?name=My%20League");
    expect(within(bar).getByRole("button", { name: "More" })).toBeInTheDocument();
    expect(document.getElementById("shell-action-slot")).not.toBeNull();
  });

  it("outside a league shows Home / Fantasy Sim / News / More", () => {
    nav.pathname = "/leagues";
    nav.leagueId = undefined;
    render(<AppShellBar />);
    const bar = screen.getByRole("navigation", { name: "Main sections" });
    expect(within(bar).getAllByRole("link").map((l) => l.textContent)).toEqual(["Your leagues", "Fantasy Sim", "News"]);
    expect(within(bar).getByRole("link", { name: "Your leagues" })).toHaveAttribute("aria-current", "page");
    nav.pathname = "/dashboard/league-1";
    nav.leagueId = "league-1";
  });

  it("More opens the full grouped menu with Pro markers from the shared catalog", () => {
    render(<AppShellBar />);
    fireEvent.click(screen.getByRole("button", { name: "More" }));
    const menu = screen.getByRole("navigation", { name: "All pages" });
    // Pages the bar does not show lead; the ones it does fold into one "Sections" group (derived from pageFamilies).
    const lead = within(menu).getByRole("region", { name: "League tools" });
    expect(within(lead).getByRole("link", { name: /GM Plan/ })).toBeInTheDocument();
    expect(within(lead).queryByRole("link", { name: /Waivers/ })).toBeNull();
    const sections = within(menu).getByRole("region", { name: "Sections" });
    expect(within(sections).getByRole("link", { name: /Waivers/ })).toBeInTheDocument();
    expect(within(menu).getByRole("link", { name: /Today/ })).toBeInTheDocument();
    expect(within(menu).getByRole("link", { name: /Fantasy Sim/ })).toBeInTheDocument();
    expect(within(menu).getAllByTestId("nav-pro-marker").length).toBeGreaterThan(0);
  });
});
