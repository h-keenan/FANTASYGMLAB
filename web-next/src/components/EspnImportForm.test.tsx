import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SleeperImportForm } from "./SleeperImportForm";
import { useAuth } from "@/context/AuthContext";
import { trackUse } from "@/lib/analytics";
import { api, type EspnLeaguePreviewResponse } from "@/lib/api";

vi.mock("@/context/AuthContext", () => ({
  useAuth: vi.fn(),
}));

vi.mock("@/lib/analytics", () => ({
  trackFeatureUse: vi.fn(),
  trackUse: vi.fn(),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      previewEspnLeague: vi.fn(),
      previewImportedLeague: vi.fn(),
      saveLeague: vi.fn(),
    },
  };
});

const PREVIEW: EspnLeaguePreviewResponse = {
  ok: true,
  reason: "",
  message: "",
  league: { league_key: "espn:42654852:2026", espn_league_id: "42654852", season: "2026", name: "FFLR Test League", team_count: 2 },
  teams: [
    { roster_id: "1", team_name: "Austin Astronauts", owner_name: "K5cents", player_count: 16, matched_player_count: 13 },
    { roster_id: "2", team_name: "Boston Buzzards", owner_name: "K5cents", player_count: 16, matched_player_count: 15 },
  ],
  diagnostics: {
    teams_found: 2,
    total_espn_players_seen: 32,
    canonical_matched_count: 28,
    unmatched_count: 4,
    matched_rate: 0.875,
    unmatched_examples: [],
  },
  features: [
    { feature: "My Team", status: "available", note: "" },
    { feature: "Waivers", status: "not_available", note: "Not available for ESPN leagues yet." },
  ],
};

function openEspn() {
  render(<SleeperImportForm onLeagueChosen={onLeagueChosen} />);
  fireEvent.click(screen.getByRole("button", { name: "ESPN" }));
}

const onLeagueChosen = vi.fn();

describe("ESPN import in the Connect League flow", () => {
  beforeEach(() => {
    vi.mocked(useAuth).mockReturnValue({
      session: { user: { id: "user-1" } } as never,
      signInAsGuest: vi.fn(),
    } as unknown as ReturnType<typeof useAuth>);
    vi.mocked(api.previewEspnLeague).mockReset();
    vi.mocked(api.saveLeague).mockReset();
    onLeagueChosen.mockReset();
  });

  it("defaults to Sleeper and switches to the ESPN form, which asks for no private-league cookies", () => {
    render(<SleeperImportForm onLeagueChosen={onLeagueChosen} />);
    expect(screen.getByPlaceholderText("Sleeper username")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "ESPN" }));
    expect(screen.getByLabelText(/espn league id/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/swid|espn_s2/i)).toBeNull();
    expect(screen.getByText(/private espn leagues aren't supported yet/i)).toBeInTheDocument();
  });

  it("rejects a non-numeric league id without calling the API", () => {
    openEspn();
    fireEvent.change(screen.getByLabelText(/espn league id/i), { target: { value: "my league" } });
    fireEvent.click(screen.getByRole("button", { name: /find my espn league/i }));
    expect(screen.getByRole("alert")).toHaveTextContent(/leagueId=/);
    expect(api.previewEspnLeague).not.toHaveBeenCalled();
  });

  it("previews, requires a team pick, and saves the ESPN league with that team", async () => {
    vi.mocked(api.previewEspnLeague).mockResolvedValue(PREVIEW);
    vi.mocked(api.saveLeague).mockResolvedValue({ ok: true, reason: "", cap: 1 });
    openEspn();

    fireEvent.change(screen.getByLabelText(/espn league id/i), { target: { value: "42654852" } });
    fireEvent.click(screen.getByRole("button", { name: /find my espn league/i }));

    await waitFor(() => expect(screen.getByText("FFLR Test League")).toBeInTheDocument());
    expect(screen.getByText(/28 of 32 rostered players matched/i)).toBeInTheDocument();
    expect(screen.getByText(/not available for espn leagues yet:/i).parentElement).toHaveTextContent("Waivers");

    const save = screen.getByRole("button", { name: /add this league/i });
    expect(save).toBeDisabled();
    fireEvent.click(screen.getByRole("radio", { name: /boston buzzards/i }));
    fireEvent.click(save);

    await waitFor(() => expect(onLeagueChosen).toHaveBeenCalledWith("espn:42654852:2026", "FFLR Test League"));
    expect(api.saveLeague).toHaveBeenCalledWith({
      leagueId: "espn:42654852:2026",
      leagueName: "FFLR Test League",
      rosterId: "2",
      makeDefault: true,
    });
  });

  it("imports an MFL league through the shared form, listing players left unmatched", async () => {
    vi.mocked(api.previewImportedLeague).mockResolvedValue({
      ...PREVIEW,
      platform: "mfl",
      league: { league_key: "mfl:10015:2025", external_league_id: "10015", season: "2025", name: "Dynasty Pioneer", team_count: 2 },
      diagnostics: {
        teams_found: 2,
        total_players_seen: 10,
        canonical_matched_count: 9,
        unmatched_count: 1,
        matched_rate: 0.9,
        unmapped_players: [{ name: "Zzyzx Unmappable", position: "WR", team: "", fantasy_team: "Austin Astronauts", reason: "no_unique_match" }],
      },
    });
    vi.mocked(api.saveLeague).mockResolvedValue({ ok: true, reason: "", cap: 1 });
    render(<SleeperImportForm onLeagueChosen={onLeagueChosen} />);
    fireEvent.click(screen.getByRole("button", { name: "MFL" }));
    fireEvent.change(screen.getByLabelText(/mfl league id/i), { target: { value: "10015" } });
    fireEvent.click(screen.getByRole("button", { name: /find my mfl league/i }));

    await waitFor(() => expect(screen.getByText("Dynasty Pioneer")).toBeInTheDocument());
    expect(api.previewImportedLeague).toHaveBeenCalledWith("mfl", "10015", expect.any(Number));
    expect(screen.getByText(/9 of 10 rostered players matched/i)).toBeInTheDocument();
    expect(screen.getByText(/zzyzx unmappable \(WR\)/i)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("radio", { name: /boston buzzards/i }));
    fireEvent.click(screen.getByRole("button", { name: /add this league/i }));
    await waitFor(() => expect(onLeagueChosen).toHaveBeenCalledWith("mfl:10015:2025", "Dynasty Pioneer"));
  });

  it("shows the private-league explanation the API returns", async () => {
    vi.mocked(api.previewEspnLeague).mockResolvedValue({
      ok: false,
      reason: "private_league",
      message: "This ESPN league is private, or the league ID is wrong.",
    });
    openEspn();
    fireEvent.change(screen.getByLabelText(/espn league id/i), { target: { value: "1" } });
    fireEvent.click(screen.getByRole("button", { name: /find my espn league/i }));

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/private/i));
    expect(api.saveLeague).not.toHaveBeenCalled();
  });

  it("shows the friendly ESPN setting hint, a Retry button and emits espn_private", async () => {
    vi.mocked(trackUse).mockClear();
    vi.mocked(api.previewEspnLeague).mockResolvedValue({ ok: false, reason: "private_league", message: "x" });
    openEspn();
    fireEvent.change(screen.getByLabelText(/espn league id/i), { target: { value: "99887766" } });
    fireEvent.click(screen.getByRole("button", { name: /find my espn league/i }));

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/Make League Viewable to Public/));
    expect(trackUse).toHaveBeenCalledWith("league_import", "failed", { props: { result: "espn_private" } });
    expect(JSON.stringify(vi.mocked(trackUse).mock.calls)).not.toContain("99887766");

    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(api.previewEspnLeague).toHaveBeenCalledTimes(2));
  });

  it("does not show the private hint or Retry for a wrong id or an outage", async () => {
    vi.mocked(trackUse).mockClear();
    vi.mocked(api.previewEspnLeague).mockResolvedValueOnce({ ok: false, reason: "league_not_found", message: "Not found." });
    openEspn();
    fireEvent.change(screen.getByLabelText(/espn league id/i), { target: { value: "1" } });
    fireEvent.click(screen.getByRole("button", { name: /find my espn league/i }));
    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Not found."));
    expect(screen.queryByRole("button", { name: "Retry" })).toBeNull();
    expect(trackUse).toHaveBeenLastCalledWith("league_import", "failed", { props: { result: "espn_not_found" } });

    vi.mocked(api.previewEspnLeague).mockResolvedValueOnce({ ok: false, reason: "espn_unavailable", message: "Down." });
    fireEvent.click(screen.getByRole("button", { name: /find my espn league/i }));
    await waitFor(() => expect(trackUse).toHaveBeenLastCalledWith("league_import", "failed", { props: { result: "espn_error" } }));
  });

  it("shows the Pro upsell and does NOT open the league when the save is refused at_cap", async () => {
    vi.mocked(api.previewEspnLeague).mockResolvedValue(PREVIEW);
    vi.mocked(api.saveLeague).mockResolvedValue({ ok: false, reason: "at_cap", cap: 1 });
    openEspn();

    fireEvent.change(screen.getByLabelText(/espn league id/i), { target: { value: "42654852" } });
    fireEvent.click(screen.getByRole("button", { name: /find my espn league/i }));
    await waitFor(() => expect(screen.getByText("FFLR Test League")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("radio", { name: /boston buzzards/i }));
    fireEvent.click(screen.getByRole("button", { name: /add this league/i }));

    await waitFor(() => expect(screen.getByText("Free includes 1 league. Upgrade to add more.")).toBeInTheDocument());
    expect(screen.getByRole("link", { name: /upgrade/i })).toHaveAttribute("href", "/premium");
    expect(onLeagueChosen).not.toHaveBeenCalled();
  });

  it("shows the mapped message and does NOT open the league on mapping_too_low", async () => {
    vi.mocked(api.previewEspnLeague).mockResolvedValue(PREVIEW);
    vi.mocked(api.saveLeague).mockResolvedValue({ ok: false, reason: "mapping_too_low", cap: 0 });
    openEspn();

    fireEvent.change(screen.getByLabelText(/espn league id/i), { target: { value: "42654852" } });
    fireEvent.click(screen.getByRole("button", { name: /find my espn league/i }));
    await waitFor(() => expect(screen.getByText("FFLR Test League")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("radio", { name: /boston buzzards/i }));
    fireEvent.click(screen.getByRole("button", { name: /add this league/i }));

    await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent(/too few of this league/i));
    expect(onLeagueChosen).not.toHaveBeenCalled();
  });
});
