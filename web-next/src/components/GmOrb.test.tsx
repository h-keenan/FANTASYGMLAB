import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { GmOrb } from "./GmOrb";
import { useAuth } from "@/context/AuthContext";
import { trackFeatureUse } from "@/lib/analytics";
import { api } from "@/lib/api";

const openPlayer = vi.fn();
vi.mock("@/context/PlayerQuickViewContext", () => ({
  usePlayerQuickView: () => ({ openPlayer, closePlayer: vi.fn() }),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, api: { ...actual.api, getLeagueRankings: vi.fn() } };
});

vi.mock("@/context/AuthContext", () => ({
  useAuth: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard/league-1",
  useParams: () => ({ leagueId: "league-1" }),
  useSearchParams: () => new URLSearchParams(),
}));

// Real analytics (lib/analytics.ts) does its own fire-and-forget network
// call -- irrelevant to what this file is testing (founder gating / wiring)
// and would otherwise hit a real `fetch` during these component tests.
vi.mock("@/lib/analytics", () => ({
  trackFeatureUse: vi.fn(),
}));

type MockSession = { user: { id: string; app_metadata?: Record<string, unknown> } };

function mockAuth(session: MockSession | null) {
  vi.mocked(useAuth).mockReturnValue({
    session: session as never,
    loading: false,
    signIn: vi.fn(),
    signUp: vi.fn(),
    signInWithOAuth: vi.fn(),
    signInAsGuest: vi.fn(),
    signOut: vi.fn(),
    deleteAccount: vi.fn(),
    isGuest: false,
  });
}

/**
 * Covers coridian_'s 2026-10-19 ask ("just put it in the orb menu for the
 * specific account(s) listed on supabase") — the GM orb's "Founder" section
 * must only appear for a session whose own Supabase Auth app_metadata
 * carries `founder_ops: true`. This is a client-side UX nicety only: the
 * real authorization boundary is GET /v1/founder/analytics's server-side
 * 403 for anyone without that same claim (services/mobile_api_service.py),
 * covered separately in tests/test_mobile_api_service.py.
 */
describe("GmOrb founder gating", () => {
  it("does not show Founder Analytics for an ordinary signed-in account", () => {
    mockAuth({ user: { id: "user-1" } });
    render(<GmOrb />);

    fireEvent.click(screen.getByLabelText("Open GM menu"));

    expect(screen.queryByText("Founder Analytics")).not.toBeInTheDocument();
  });

  it("does not show Founder Analytics for an account with only a client-editable user_metadata flag", () => {
    // Guards against ever reading the wrong metadata bag — user_metadata is
    // editable by the account itself, unlike app_metadata.
    mockAuth({ user: { id: "user-1", app_metadata: {} } });
    render(<GmOrb />);

    fireEvent.click(screen.getByLabelText("Open GM menu"));

    expect(screen.queryByText("Founder Analytics")).not.toBeInTheDocument();
  });

  it("shows Founder Analytics for a session whose app_metadata carries founder_ops", () => {
    mockAuth({ user: { id: "founder-1", app_metadata: { founder_ops: true } } });
    render(<GmOrb />);

    fireEvent.click(screen.getByLabelText("Open GM menu"));

    expect(screen.getByText("Founder Analytics")).toBeInTheDocument();
  });

  it("renders nothing at all when there is no session", () => {
    mockAuth(null);
    const { container } = render(<GmOrb />);

    expect(container).toBeEmptyDOMElement();
  });
});

/**
 * The real bug this wiring fixes: web-next never called into
 * modules/launch_analytics.py at all, so `analytics_events` stayed empty
 * despite real traffic (services/mobile_api_service.py's new
 * POST /v1/analytics/event is the fix). This is one of the handful of real
 * call sites wired for that pass -- see lib/analytics.ts's own test file
 * for coverage of the client module itself.
 */
describe("GmOrb analytics wiring", () => {
  it("fires gm_orb_opened every time the orb is opened", () => {
    mockAuth({ user: { id: "user-1" } });
    render(<GmOrb />);

    fireEvent.click(screen.getByLabelText("Open GM menu"));

    expect(trackFeatureUse).toHaveBeenCalledWith("gm_orb_opened", {
      leagueId: "league-1",
      dedupe: false,
    });
  });
});

/** Tap-depth audit 2026-10 #3: the orb's search matches destinations and,
 * with a league open, player names; a player opens Player Quick View. */
describe("GmOrb search", () => {
  it("matches league players by name and opens their quick view", async () => {
    mockAuth({ user: { id: "user-1" } });
    vi.mocked(api.getLeagueRankings).mockResolvedValue({
      ok: true,
      players: [
        { player_id: "p1", name: "Travis Kelce", position: "TE", team: "KC" },
        { player_id: "p2", name: "Mike Evans", position: "WR", team: "TB" },
      ],
    } as never);
    render(<GmOrb />);

    fireEvent.click(screen.getByLabelText("Open GM menu"));
    fireEvent.change(screen.getByLabelText("Search destinations and players"), { target: { value: "kelce" } });

    const playerRow = await screen.findByRole("button", { name: /Travis Kelce/ });
    expect(screen.queryByText("Mike Evans")).not.toBeInTheDocument();
    expect(api.getLeagueRankings).toHaveBeenCalledWith("league-1");

    fireEvent.click(playerRow);
    expect(openPlayer).toHaveBeenCalledWith(
      expect.objectContaining({ player_id: "p1", leagueId: "league-1", sourceLabel: "Search" }),
    );
  });

  it("filters destinations without fetching players for a one-letter query", () => {
    mockAuth({ user: { id: "user-1" } });
    vi.mocked(api.getLeagueRankings).mockClear();
    render(<GmOrb />);

    fireEvent.click(screen.getByLabelText("Open GM menu"));
    fireEvent.change(screen.getByLabelText("Search destinations and players"), { target: { value: "w" } });

    expect(screen.getByText("Waivers")).toBeInTheDocument();
    expect(screen.queryByText("General")).not.toBeInTheDocument();
    expect(api.getLeagueRankings).not.toHaveBeenCalled();
  });
});
