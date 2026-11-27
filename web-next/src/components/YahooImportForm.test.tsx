import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SleeperImportForm } from "./SleeperImportForm";
import { useAuth } from "@/context/AuthContext";
import { api, type EspnLeaguePreviewResponse } from "@/lib/api";

vi.mock("@/context/AuthContext", () => ({ useAuth: vi.fn() }));
vi.mock("@/lib/analytics", () => ({ trackFeatureUse: vi.fn(), trackUse: vi.fn() }));
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      getYahooStatus: vi.fn(),
      startYahooOAuth: vi.fn(),
      disconnectYahoo: vi.fn(),
      listYahooLeagues: vi.fn(),
      previewYahooLeague: vi.fn(),
      saveLeague: vi.fn(),
    },
  };
});

const LEAGUE = { league_key: "yahoo:461.l.12345:2026", yahoo_league_key: "461.l.12345", name: "Sunday Funday", season: "2026", team_count: 2 };
const PREVIEW: EspnLeaguePreviewResponse = {
  ok: true,
  reason: "",
  message: "",
  platform: "yahoo",
  league: { league_key: LEAGUE.league_key, external_league_id: "461.l.12345", season: "2026", name: "Sunday Funday", team_count: 2 },
  teams: [
    { roster_id: "1", team_name: "Gridiron Ghosts", owner_name: "alex", player_count: 9, matched_player_count: 8 },
    { roster_id: "2", team_name: "Bye Week Bandits", owner_name: "sam", player_count: 5, matched_player_count: 5 },
  ],
  diagnostics: { teams_found: 2, total_players_seen: 14, canonical_matched_count: 13, unmatched_count: 1, matched_rate: 0.93 },
  features: [
    { feature: "My Team", status: "available", note: "" },
    { feature: "Waivers", status: "not_available", note: "Not available for Yahoo leagues yet." },
  ],
};
const onLeagueChosen = vi.fn();

function openYahoo() {
  render(<SleeperImportForm onLeagueChosen={onLeagueChosen} />);
  fireEvent.click(screen.getByRole("button", { name: /^Yahoo/ }));
}

describe("Yahoo import in the Connect League flow", () => {
  beforeEach(() => {
    vi.mocked(useAuth).mockReturnValue({
      session: { user: { id: "user-1" } } as never,
      signInAsGuest: vi.fn(),
    } as unknown as ReturnType<typeof useAuth>);
    for (const fn of [api.getYahooStatus, api.startYahooOAuth, api.listYahooLeagues, api.previewYahooLeague, api.saveLeague, api.disconnectYahoo]) vi.mocked(fn).mockReset();
    onLeagueChosen.mockReset();
  });

  it("offers Connect Yahoo when not connected and starts OAuth", async () => {
    vi.mocked(api.getYahooStatus).mockResolvedValue({ ok: true, available: true, connected: false });
    vi.mocked(api.startYahooOAuth).mockResolvedValue({ ok: false, reason: "not_configured", message: "Connecting Yahoo isn't available right now." });
    openYahoo();
    fireEvent.click(screen.getByRole("button", { name: /about yahoo/i }));
    expect(screen.getByText(/Waiver and trade suggestions aren't available for Yahoo leagues yet/)).toBeInTheDocument();
    fireEvent.click(await screen.findByRole("button", { name: "Connect Yahoo" }));
    await waitFor(() => expect(api.startYahooOAuth).toHaveBeenCalledWith("web"));
    expect(await screen.findByText("Connecting Yahoo isn't available right now.")).toBeInTheDocument();
  });

  it("says so honestly when the server has no Yahoo app configured", async () => {
    vi.mocked(api.getYahooStatus).mockResolvedValue({ ok: true, available: false, connected: false });
    openYahoo();
    expect(await screen.findByText("Connecting Yahoo isn't available right now.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Connect Yahoo" })).toBeNull();
  });

  it("lists the user's leagues, previews one, and saves with the picked team", async () => {
    vi.mocked(api.getYahooStatus).mockResolvedValue({ ok: true, available: true, connected: true });
    vi.mocked(api.listYahooLeagues).mockResolvedValue({ ok: true, leagues: [LEAGUE] });
    vi.mocked(api.previewYahooLeague).mockResolvedValue(PREVIEW);
    vi.mocked(api.saveLeague).mockResolvedValue({ ok: true } as never);
    openYahoo();
    fireEvent.click(await screen.findByRole("button", { name: /Sunday Funday/ }));
    await waitFor(() => expect(api.previewYahooLeague).toHaveBeenCalledWith(LEAGUE.league_key));
    expect(await screen.findByText(/Not available for Yahoo leagues yet:/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("radio", { name: /Bye Week Bandits/ }));
    fireEvent.click(screen.getByRole("button", { name: /add this league/i }));
    await waitFor(() => expect(onLeagueChosen).toHaveBeenCalledWith(LEAGUE.league_key, "Sunday Funday"));
    expect(api.saveLeague).toHaveBeenCalledWith(expect.objectContaining({ leagueId: LEAGUE.league_key, rosterId: "2" }));
  });

  it("asks to reconnect when Yahoo refused the stored login", async () => {
    vi.mocked(api.getYahooStatus).mockResolvedValue({ ok: true, available: true, connected: true });
    vi.mocked(api.listYahooLeagues).mockResolvedValue({ ok: false, reason: "reconnect_needed" });
    openYahoo();
    expect(await screen.findByText(/Your Yahoo connection expired/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Connect Yahoo" })).toBeInTheDocument();
  });
});
