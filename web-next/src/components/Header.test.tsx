import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { EvaluationLensButton, Header } from "./Header";
import { useAuth } from "@/context/AuthContext";
import { supabase } from "@/lib/supabase";

/**
 * Covers two real, confirmed bugs from a coridian_ screenshot: the header
 * showing a raw Sleeper league_id instead of a league name, and the
 * "Dynasty ▾" lens dropdown clipping off the right edge of the screen.
 */

const mockSearchParams = { get: vi.fn() };
const mockParams: { leagueId?: string } = { leagueId: "league-7" };

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard/league-7",
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
describe("Header league name", () => {
  it("shows the real league name from the `?name=` query param (how all 3 previously-broken links now arrive)", async () => {
    mockSearchParams.get.mockImplementation((key: string) => (key === "name" ? "Dynasty Overlords" : null));
    render(<Header />);

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
    render(<Header />);

    expect(await screen.findByRole("button", { name: /Dynasty Overlords/ })).toBeInTheDocument();
  });

  it("falls back to the raw id only when no name is available anywhere (saved_leagues empty, no query param)", async () => {
    mockSearchParams.get.mockReturnValue(null);
    mockSavedLeagues([]);
    render(<Header />);

    expect(await screen.findByRole("button", { name: /league-7/ })).toBeInTheDocument();
  });
});

// Bug 2: EvaluationLensButton's dropdown panel was hardcoded to one static
// anchor. A static `right-0` swap alone would have silently reintroduced a
// DIFFERENT real, previously-fixed bug (e95fc345): on a narrow phone the
// header's flex-wrap row can leave this button alone near the left edge,
// where a `right-0` panel has nowhere to grow but off-screen to the left.
// The fix measures the button's real position and picks whichever anchor
// keeps the panel on-screen in both layouts.
describe("EvaluationLensButton dropdown anchor", () => {
  function clickWithRect(rect: Partial<DOMRect>) {
    const button = screen.getByRole("button", { name: /Dynasty/ });
    vi.spyOn(button, "getBoundingClientRect").mockReturnValue({
      top: 0,
      bottom: 0,
      width: 0,
      height: 0,
      x: 0,
      y: 0,
      toJSON: () => ({}),
      ...rect,
    } as DOMRect);
    fireEvent.click(button);
  }

  it("anchors right-0 when the button sits near the right edge of a wide viewport (the normal right-aligned header cluster)", () => {
    window.innerWidth = 1280;
    render(<EvaluationLensButton leagueId="league-7" />);

    clickWithRect({ left: 1100, right: 1180 });

    const menu = screen.getByRole("menu");
    expect(menu.className).toContain("right-0");
    expect(menu.className).not.toContain("left-0");
  });

  it("anchors left-0 when the row wraps and the button lands near the left edge of a narrow viewport", () => {
    window.innerWidth = 375;
    render(<EvaluationLensButton leagueId="league-7" />);

    clickWithRect({ left: 8, right: 90 });

    const menu = screen.getByRole("menu");
    expect(menu.className).toContain("left-0");
    expect(menu.className).not.toContain("right-0");
  });
});
