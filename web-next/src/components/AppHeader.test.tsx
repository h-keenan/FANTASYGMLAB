import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AppHeader } from "./AppHeader";
import { useAuth } from "@/context/AuthContext";
import { supabase } from "@/lib/supabase";

/**
 * Covers two real, confirmed bugs from a coridian_ screenshot: the header
 * showing a raw Sleeper league_id instead of a league name, and the
 * "Dynasty ▾" lens dropdown clipping off the right edge of the screen.
 */

const mockSearchParams = { get: vi.fn() };
const mockParams: { leagueId?: string } = { leagueId: "league-7" };

const nav = vi.hoisted(() => ({ pathname: "/dashboard/league-7" }));
vi.mock("next/navigation", () => ({
  usePathname: () => nav.pathname,
  useParams: () => mockParams,
  useSearchParams: () => mockSearchParams,
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

vi.mock("@/context/AuthContext", () => ({
  useAuth: vi.fn(),
}));

vi.mock("@/lib/supabase", () => ({
  supabase: { from: vi.fn() },
}));

// Real VALUATION_LENS_OPTIONS (for EvaluationLensButton's own options list),
// but a fixed, un-mocked-provider-needing `useValuationLens` — these tests
// aren't about the lens value itself, just the header's league-name
// resolution and the lens dropdown's anchoring.
vi.mock("@/context/ValuationLensContext", async () => {
  const actual =
    await vi.importActual<typeof import("@/context/ValuationLensContext")>("@/context/ValuationLensContext");
  return {
    ...actual,
    useValuationLens: () => ({ lens: "Dynasty", setLens: vi.fn() }),
  };
});

function mockSavedLeagues(rows: { league_id: string; league_name: string | null }[]) {
  vi.mocked(supabase.from).mockReturnValue({
    select: vi.fn().mockResolvedValue({ data: rows }),
  } as never);
}

beforeEach(() => {
  vi.mocked(useAuth).mockReturnValue({
    session: null,
    loading: false,
    signIn: vi.fn(),
    signUp: vi.fn(),
    signInWithOAuth: vi.fn(),
    signInAsGuest: vi.fn(),
    signOut: vi.fn(),
    deleteAccount: vi.fn(),
    upgradeGuestWithEmail: vi.fn(),
    callbackNotice: null,
    isGuest: false,
  } as never);
  mockParams.leagueId = "league-7";
  mockSearchParams.get.mockReset();
  mockSavedLeagues([]);
});

// Bug 1: HeaderLeagueControls used to compute `leagueName` purely from the
// `?name=` query param with no fallback, so any link into a `[leagueId]`
// route that forgot it (PortfolioContent.tsx's "Watch live draft →",
// GuessThePlayerCard.tsx's and GuessThePlayerNameMatchCard.tsx's "League
// Leaderboard →") left the header showing the raw numeric league_id.
describe("AppHeader league name", () => {
  it("shows the real league name from the `?name=` query param (how all 3 previously-broken links now arrive)", async () => {
    mockSearchParams.get.mockImplementation((key: string) => (key === "name" ? "Dynasty Overlords" : null));
    render(<AppHeader />);

    expect(await screen.findByRole("button", { name: /Dynasty Overlords/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^league-7/ })).not.toBeInTheDocument();
  });

  // The structural fix: even without `?name=` at all, the header resolves
  // the real name from the same `saved_leagues` data the switcher's own
  // dropdown already fetches, instead of silently displaying the raw id.
  // This is what makes the whole bug class unable to recur even if a
  // future call site forgets the query param.
  it("resolves the real league name from saved_leagues when `?name=` is absent", async () => {
    mockSearchParams.get.mockReturnValue(null);
    mockSavedLeagues([{ league_id: "league-7", league_name: "Dynasty Overlords" }]);
    render(<AppHeader />);

    expect(await screen.findByRole("button", { name: /Dynasty Overlords/ })).toBeInTheDocument();
  });

  it("falls back to a friendly name (never the raw id) when no name is available anywhere (saved_leagues empty, no query param)", async () => {
    mockSearchParams.get.mockReturnValue(null);
    mockSavedLeagues([]);
    render(<AppHeader />);

    expect(await screen.findByRole("button", { name: /Your league/ })).toBeInTheDocument();
  });
});

describe("AppHeader (wide / signed-out bar)", () => {
  it("an immersive page (live draft) gets the minimal bar: no league identity, search or bell", async () => {
    nav.pathname = "/live-draft/league-7";
    render(<AppHeader />);
    expect(screen.queryByTestId("league-identity")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Search players/ })).not.toBeInTheDocument();
    nav.pathname = "/dashboard/league-7";
  });
});
