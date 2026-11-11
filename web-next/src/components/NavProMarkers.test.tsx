import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DesktopSidebar } from "./DesktopSidebar";
import { GmOrb } from "./GmOrb";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";

vi.mock("@/context/AuthContext", () => ({ useAuth: vi.fn() }));
vi.mock("@/context/PlayerQuickViewContext", () => ({
  usePlayerQuickView: () => ({ openPlayer: vi.fn(), closePlayer: vi.fn() }),
}));
vi.mock("@/lib/analytics", () => ({ trackFeatureUse: vi.fn() }));
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, api: { ...actual.api, getMe: vi.fn(), getLeagueRankings: vi.fn() } };
});
vi.mock("next/navigation", () => ({
  usePathname: () => "/league-rankings/L1",
  useParams: () => ({ leagueId: "L1" }),
  useSearchParams: () => new URLSearchParams("name=Test%20League"),
}));

let n = 0;
function signIn(entitlement: "free" | "premium") {
  n += 1;
  vi.mocked(useAuth).mockReturnValue({ session: { user: { id: `u${n}`, app_metadata: {} } }, loading: false } as never);
  vi.mocked(api.getMe).mockResolvedValue({
    ok: true,
    user: { id: `u${n}`, email: "", entitlement, sleeper_username: "", profile_status: "ok", league_cap: 1 },
    premium_benefits: [],
  } as never);
}

describe("nav Pro lock markers and account rows", () => {
  beforeEach(() => vi.clearAllMocks());

  it("sidebar marks the paid destinations for a Free account", async () => {
    signIn("free");
    render(<DesktopSidebar />);
    await waitFor(() => expect(screen.getAllByTestId("nav-pro-marker").length).toBeGreaterThan(0));
    for (const label of ["Draft Center", "Live Draft", "Commissioner", "Portfolio"]) {
      expect(screen.getByText(label).closest("a")?.querySelector("[data-testid='nav-pro-marker']")).not.toBeNull();
    }
    expect(screen.getByText("Trade Hub").closest("a")?.querySelector("[data-testid='nav-pro-marker']")).toBeNull();
  });

  it("sidebar shows no markers for a Pro account and keeps the Pro and Account rows", async () => {
    signIn("premium");
    render(<DesktopSidebar />);
    await waitFor(() => expect(api.getMe).toHaveBeenCalled());
    expect(screen.queryByTestId("nav-pro-marker")).toBeNull();
    expect(screen.getByRole("link", { name: "Pro" })).toHaveAttribute("href", "/premium");
    expect(screen.getByRole("link", { name: "Account" })).toHaveAttribute("href", "/account");
  });

  it("has no separate rows for pages that are tabs (Playoff Odds, Trade History, College Scouting)", () => {
    signIn("premium");
    render(<DesktopSidebar />);
    for (const label of ["Playoff Odds", "Trade History", "College Scouting"]) expect(screen.queryByText(label)).toBeNull();
  });

  it("the orb carries a visible GM label and the same Pro markers", async () => {
    signIn("free");
    render(<GmOrb />);
    const orb = screen.getByRole("button", { name: "Open GM menu" });
    expect(orb).toHaveTextContent("GM");
    orb.click();
    await waitFor(() => expect(screen.getAllByTestId("nav-pro-marker").length).toBeGreaterThan(0));
    expect(screen.getByRole("link", { name: /^Account/ })).toHaveAttribute("href", "/account");
  });
});
