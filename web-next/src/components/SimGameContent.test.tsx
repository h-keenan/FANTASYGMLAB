import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SimGameContent } from "./SimGameContent";
import { api } from "@/lib/api";
import type { SimGame, SimGameOptionsResponse, SimGamePlayer, SimHomeResponse, SimLineupResponse, SimTeamRosterResponse } from "@/lib/simGame";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

const savedLeagues = [
  { league_id: "111", league_name: "Dynasty Dogs" },
  { league_id: "espn:5:2026", league_name: "ESPN Thing" },
];
vi.mock("@/lib/supabase", () => ({
  supabase: { from: () => ({ select: () => Promise.resolve({ data: savedLeagues, error: null }) }) },
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  const names = [
    "getSimGameOptions", "getSimLeagueTeams", "listSimGames", "createSimGame", "getSimGame", "deleteSimGame", "getSimDraft", "simDraftPick", "simDraftAuto",
    "putSimDraftQueue", "getSimGamePlayers", "getSimGamePlayer", "getSimGameTeam", "getSimHome", "getSimLineup", "putSimLineup", "autoSimLineup",
    "claimSimWaiver", "cancelSimWaiver", "cutSimPlayer", "previewSimTrade", "sendSimTrade", "getSimInbox", "respondSimInbox",
    "advanceSimGame", "revertSimWeek", "getSimLeague", "getSimLeagueRosters", "getSimTeamHistory", "getSimToOptions", "simToGame", "undoSimTo", "getSimGameResult",
  ];
  return { ...actual, api: { ...actual.api, ...Object.fromEntries(names.map((n) => [n, vi.fn()])) } };
});

const mocked = api as unknown as Record<string, ReturnType<typeof vi.fn>>;

function player(id: string, pos: SimGamePlayer["pos"], name: string): SimGamePlayer {
  return { id, name, pos, team: "KC", age: 25, adp: 5, value: 80, projection: 14.2, floor: 7, ceiling: 24, status: "healthy", out_weeks: 0, bye_week: 9, owner: { type: "free_agent" } };
}

const SETTINGS = { teams: 12, scoring: "ppr", difficulty: "normal", regular_weeks: 14, playoff_teams: 6, playoff_weeks: 3, trade_deadline_week: 10, roster_limit: 16, rounds: 14, slots: ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "K"], user_slot: 3, auto_lineup: false } as SimGame["settings"];

function game(overrides: Partial<SimGame> = {}): SimGame {
  return {
    id: "g1", status: "in_season", week: 4, phase: "regular_season", round: null, seed: 1, engine_version: "game-1.0.0", settings: SETTINGS,
    you: { team_id: "3", name: "My Team", wins: 2, losses: 1, ties: 0, pf: 361.4, pa: 330.2, rank: 4, seed: null },
    this_week: { week: 4, opponent: { team_id: "7", name: "Rivals", persona_id: "passive" }, bye: false, your_projection: 121.4, opponent_projection: 117.9 },
    pending: { claims: 0, inbox: 0, lineup_warnings: 0, roster_size: 16, roster_limit: 16, cuts_needed: 0 },
    can_trade: true, trade_deadline_week: 10, grade_letter: null, created_at: "", updated_at: "", ...overrides,
  };
}

const lite = (g: SimGame) => ({ id: g.id, seed: 1, engine_version: "x", settings: g.settings, status: g.status, current_week: g.week, difficulty: "normal" as const, grade_letter: null, event_count: 3, created_at: "", updated_at: "" });

const options = (over: Partial<SimGameOptionsResponse> = {}): SimGameOptionsResponse => ({
  ok: true, reason: "", is_premium: true, upsell: null, preview: null, max_games: 3,
  options: { teams: { values: [8, 10, 12], default: 12 }, scoring: { values: ["ppr", "half", "std"], default: "ppr" }, difficulty: { values: ["easy", "normal", "hard"], default: "normal" }, user_slot: { min: 1, max: 12, default: null }, auto_lineup: { default: false } },
  season: { regular_weeks: 14, playoff_weeks: 3, playoff_teams: 6, trade_deadline_week: 10, roster_limit: 16, draft_rounds: 14, slots: SETTINGS.slots },
  ...over,
});

const lineup: SimLineupResponse = {
  ok: true, reason: "", week: 4, slots: [{ slot: "QB", player: player("1", "QB", "Quinn Back") }, { slot: "RB", player: player("8", "RB", "Ray Starter") }], bench: [player("2", "RB", "Benny Bench")],
  projected_total: 121.4, warnings: [], roster_size: 16, roster_limit: 16, opponent: null, locked: false,
};

const star = (id: string, pos: SimGamePlayer["pos"], name: string, over: Partial<SimGamePlayer> = {}) => ({ ...player(id, pos, name), ...over });

const home: SimHomeResponse = {
  ok: true, reason: "", week: 4, phase: "regular_season",
  matchup: {
    week: 4, bye: false, kind: "regular",
    opponent: { team_id: "7", name: "Rivals", persona_id: "passive", record: { wins: 2, losses: 1, ties: 0, pf: 340, pa: 300, rank: 3 }, persona: { id: "passive", label: "Passive", blurb: "Rarely deals." } },
    you_record: { wins: 2, losses: 1, ties: 0, pf: 361.4, pa: 330.2, rank: 4 },
    you_projection: 121.4, opp_projection: 117.9, win_prob: 0.62,
    rows: [
      { slot: "QB", you: star("1", "QB", "Quinn Back"), opp: star("5", "QB", "Otis Opp") },
      { slot: "RB", you: star("2", "RB", "Hurt Harry", { status: "out", projection: 0, out_weeks: 2 }), opp: star("6", "RB", "Ray Rival") },
    ],
    you_flagged: 1, opp_flagged: 0,
  },
  checklist: [
    { id: "lineup", label: "Set your lineup", detail: "1 starter slot need attention (out, on bye or empty).", done: false, target: "team", severity: "danger" },
    { id: "offers", label: "Answer trade offers", detail: "2 offers waiting in your inbox.", done: false, target: "trades", severity: "accent" },
  ],
  inbox: { count: 2, open: true, items: [] },
  waiver_suggestions: [{ player: star("9", "RB", "Wally Wire"), gain_now: 7.5, gain_ros: 1, reasons: ["Covers Hurt Harry (out): +7.5 pts this week"], drop: null, covers: null, for_slot: "RB1" }],
  bye_alerts: [{ week: 7, weeks_away: 3, slot: "WR", pos_label: "WR1", player: star("3", "WR", "Wes Receiver", { bye_week: 7 }), covered: false, covered_by: null, replacements: [star("11", "WR", "Fill Ford")], message: "Your WR1 Wes Receiver is on bye in Week 7. Look at the wire for a fill-in: Fill Ford." }],
  injuries: [{ player: star("2", "RB", "Hurt Harry", { status: "out", out_weeks: 2 }), out_weeks: 2, starting: true, note: "Hurt in Week 3" }],
  hot_cold: { hot: [{ player: star("1", "QB", "Quinn Back"), last_week: 30.2, delta: 9.1, avg: 22 }], cold: [], wire: [] },
  standings: { rows: [{ rank: 1, team_id: "7", name: "Rivals", is_you: false, wins: 2, losses: 1, ties: 0, pf: 340, pa: 300, streak: "W2" }, { rank: 2, team_id: "3", name: "My Team", is_you: true, wins: 2, losses: 1, ties: 0, pf: 361.4, pa: 330.2, streak: "L1" }], playoff_spots: 6, games_left: 11, your_rank: 2, margin: 1, in_playoffs: true },
  league: { recent: [], spotlight: null },
};

const premiumBody = { ok: true, reason: "premium_required", is_premium: false, upsell: { title: "Keep your season going", body: "Pro unlocks the rest of the season." }, preview: { weeks_left: 0, paywall_week: 4, paywalled: true } };

function openFirstGame() {
  return screen.findByRole("button", { name: /Open game/ }).then((b) => fireEvent.click(b));
}

async function openTeamTab() {
  fireEvent.click(await screen.findByRole("tab", { name: "Team" }));
}

describe("SimGameContent", () => {
  beforeEach(() => {
    window.sessionStorage.clear();
    vi.resetAllMocks();
    mocked.getSimGameOptions.mockResolvedValue(options());
    mocked.getSimGame.mockResolvedValue({ ok: true, reason: "", game: game() });
    mocked.getSimLineup.mockResolvedValue(lineup);
    mocked.getSimHome.mockResolvedValue(home);
    mocked.getSimGamePlayers.mockResolvedValue({ ok: true, reason: "", items: [], total: 0, page: 1, page_size: 40 });
  });

  it("opens on Home: matchup head to head, checklist, bye cover, waiver targets and injuries", async () => {
    mocked.listSimGames.mockResolvedValue({ ok: true, reason: "", games: [lite(game())] });
    mocked.getSimInbox.mockResolvedValue({ ok: true, reason: "", items: [] });
    mocked.getSimLeague.mockResolvedValue({ ok: true, reason: "", teams: [], standings: [] });
    mocked.getSimGameTeam.mockResolvedValue({ ok: true, reason: "", players: [] });
    render(<SimGameContent />);
    await openFirstGame();
    expect(await screen.findByTestId("sim-home")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Home" })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByTestId("win-chance")).toHaveTextContent("62%");
    // Phone layout: lineups and the secondary cards start collapsed, summary first.
    expect(screen.queryByRole("list", { name: "Lineups head to head" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /Show lineups/ }));
    fireEvent.click(screen.getByRole("button", { name: /Bye-week cover/ }));
    fireEvent.click(screen.getByRole("button", { name: /Injury report/ }));
    expect(screen.getByRole("button", { name: /Injury report/ })).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("list", { name: "Lineups head to head" }).querySelectorAll("li")).toHaveLength(2);
    expect(screen.getByText("Otis Opp")).toBeInTheDocument();
    expect(screen.getByText("What to do this week")).toBeInTheDocument();
    expect(screen.getByText("Set your lineup")).toBeInTheDocument();
    expect(screen.getByTestId("bye-alert")).toHaveTextContent("Look at the wire for a fill-in: Fill Ford");
    expect(screen.getByTestId("waiver-suggestion")).toHaveTextContent("Covers Hurt Harry (out)");
    expect(screen.getByTestId("home-injury")).toHaveTextContent("Out 2 wk");
    // a checklist row jumps to the tab that handles it
    fireEvent.click(screen.getByRole("button", { name: /Answer trade offers/ }));
    expect(await screen.findByRole("tab", { name: /Trades/ })).toHaveAttribute("aria-selected", "true");
  });

  it("Make an offer never shows an empty partner list: a failed or reasoned league load says why and retries", async () => {
    mocked.listSimGames.mockResolvedValue({ ok: true, reason: "", games: [lite(game())] });
    mocked.getSimInbox.mockResolvedValue({ ok: true, reason: "", items: [] });
    mocked.getSimGameTeam.mockResolvedValue({ ok: true, reason: "", players: [] });
    mocked.getSimLeague.mockResolvedValue({ ok: true, reason: "", teams: [], standings: [] });
    mocked.getSimLeagueRosters.mockResolvedValueOnce({ ok: true, reason: "wrong_phase", message: "Not available at this stage." }).mockResolvedValue({
      ok: true,
      reason: "",
      teams: [{ team_id: "t2", name: "Rival Rovers", is_you: false, power_rank: 1, persona: { id: "p", label: "Fair", blurb: "b" }, record: null, avg_age: 25, roster_size: 0, positions: [], strengths: [], needs: [], surplus: [], top_assets: [], players: [] }],
    });
    render(<SimGameContent />);
    await openFirstGame();
    fireEvent.click(await screen.findByRole("tab", { name: /Trades/ }));
    fireEvent.click(await screen.findByText(/Make an offer/));
    expect(await screen.findByText("Not available at this stage.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByRole("button", { name: /Rival Rovers.*Trade with this team/ })).toBeInTheDocument();
  });

  it("Home's Auto-set best lineup names the swap and refreshes the matchup, then says when it is optimal", async () => {
    mocked.listSimGames.mockResolvedValue({ ok: true, reason: "", games: [lite(game())] });
    mocked.getSimInbox.mockResolvedValue({ ok: true, reason: "", items: [] });
    mocked.getSimGameTeam.mockResolvedValue({ ok: true, reason: "", players: [] });
    mocked.getSimHome.mockResolvedValueOnce(home).mockResolvedValue({ ...home, matchup: { ...home.matchup!, rows: [home.matchup!.rows[0], { ...home.matchup!.rows[1], you: star("9", "RB", "Wally Wire") }] } });
    const beforeLineup = { ...lineup, slots: [{ slot: "QB", player: star("1", "QB", "Quinn Back") }, { slot: "RB", player: star("2", "RB", "Hurt Harry") }], projected_total: 121.4 };
    const afterLineup = { ...lineup, slots: [{ slot: "QB", player: star("1", "QB", "Quinn Back") }, { slot: "RB", player: star("9", "RB", "Wally Wire") }], projected_total: 129.4 };
    let applied = false;
    mocked.getSimLineup.mockImplementation(async () => (applied ? afterLineup : beforeLineup));
    mocked.autoSimLineup.mockImplementation(async () => {
      applied = true;
      return afterLineup;
    });
    render(<SimGameContent />);
    await openFirstGame();
    fireEvent.click(await screen.findByTestId("auto-lineup"));
    expect(await screen.findByText(/Swapped Hurt Harry for Wally Wire, \+8\.0 proj/)).toBeInTheDocument();
    expect(mocked.autoSimLineup).toHaveBeenCalledTimes(1);
    expect(await screen.findByText("Wally Wire", { selector: "span" })).toBeInTheDocument();
    fireEvent.click(await screen.findByTestId("auto-lineup"));
    await waitFor(() => expect(mocked.autoSimLineup).toHaveBeenCalledTimes(2));
    expect(await screen.findByRole("button", { name: /Lineup is optimal/ })).toBeDisabled();
  });

  it("tapping a team anywhere opens its scouting sheet with strengths and needs", async () => {
    mocked.listSimGames.mockResolvedValue({ ok: true, reason: "", games: [lite(game())] });
    const detail: SimTeamRosterResponse = {
      ok: true, reason: "", team_id: "7", players: [star("5", "QB", "Otis Opp")],
      team: { team_id: "7", name: "Rivals", is_you: false, persona: { id: "passive", label: "Passive", blurb: "Rarely deals." }, record: { wins: 2, losses: 1, ties: 0, pf: 340, pa: 300, rank: 3, streak: "W2", playoff_status: "in" }, power_rank: 4, avg_age: 25.1, roster_size: 16 },
      lineup: [{ slot: "QB", player: star("5", "QB", "Otis Opp") }], projected_total: 117.9,
      positions: [{ pos: "QB", rank: 1, teams: 12, level: "strength", depth: 1, starters: 1, strength: 20 }, { pos: "RB", rank: 11, teams: 12, level: "need", depth: 0, starters: 2, strength: 8 }],
      strengths: ["QB"], needs: ["RB"], injuries: [], recent: [], next_game: null, trade: { open: true, reason: null },
    };
    mocked.getSimGameTeam.mockResolvedValue(detail);
    render(<SimGameContent />);
    await openFirstGame();
    fireEvent.click((await screen.findAllByRole("button", { name: "Rivals. Open team" }))[0]);
    const sheet = await screen.findByTestId("team-sheet-name");
    expect(sheet).toHaveTextContent("Rivals");
    expect(mocked.getSimGameTeam).toHaveBeenCalledWith("g1", "7");
    expect(screen.getByText("Strong at QB. Needs RB.")).toBeInTheDocument();
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("tab", { name: "Trades" }));
    expect(screen.getByRole("button", { name: /Make an offer to Rivals/ })).toBeEnabled();
  });

  it("a team's sheet is its full roster in the shared rows: starters, bench by position, IR and taxi, then a prefilled Make an offer", async () => {
    mocked.listSimGames.mockResolvedValue({ ok: true, reason: "", games: [lite(game())] });
    const detail: SimTeamRosterResponse = {
      ok: true, reason: "", team_id: "7",
      players: [star("5", "QB", "Otis Opp"), star("6", "RB", "Benny Bench"), star("10", "WR", "Wide Wally"), star("11", "WR", "Wide Wendy")],
      ir: [star("12", "RB", "Hurt Harry", { status: "out", out_weeks: 5, value: 0 })], taxi: [star("13", "WR", "Rookie Ron")],
      team: { team_id: "7", name: "Rivals", is_you: false, persona: { id: "passive", label: "Passive", blurb: "Rarely deals." }, record: null, power_rank: 2, avg_age: 25, roster_size: 4 },
      lineup: [{ slot: "QB", player: star("5", "QB", "Otis Opp") }], projected_total: 117.9, positions: [], strengths: [], needs: [], injuries: [], recent: [], next_game: null, trade: { open: true, reason: null },
    };
    mocked.getSimGameTeam.mockResolvedValue(detail);
    mocked.getSimTeamHistory.mockResolvedValue({
      ok: true, reason: "", team_id: "7", team_name: "Rivals",
      draft: [{ id: "5", name: "Otis Opp", pos: "QB", round: 1, pick: 3, auto: false }], rookie_drafts: [],
      seasons: [{ season: 1, year: null, wins: 9, losses: 5, ties: 0, pf: 1500.5, pa: 1400.2, champion: true }],
      moves: [{ kind: "claim", season: 1, year: null, week: 4, offseason: false, added: { id: "9", name: "Wally Wire", pos: "RB" }, dropped: { id: "12", name: "Hurt Harry", pos: "RB" } }],
    });
    render(<SimGameContent />);
    await openFirstGame();
    fireEvent.click((await screen.findAllByRole("button", { name: "Rivals. Open team" }))[0]);
    await screen.findByTestId("team-sheet-name");
    expect(screen.getByRole("tab", { name: "Overview" })).toHaveAttribute("aria-selected", "true");
    expect(screen.queryByRole("region", { name: "Bench" })).toBeNull(); // lazy: the Roster tab has not been opened
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("tab", { name: "Roster" }));
    const lineup = screen.getByRole("region", { name: "Lineup" });
    expect(within(lineup).getByText("Otis Opp")).toBeInTheDocument();
    expect(within(lineup).getByText("Proj")).toBeInTheDocument();
    const bench = screen.getByRole("region", { name: "Bench" });
    expect(within(bench).getByRole("group", { name: "RB bench" })).toHaveTextContent("Benny Bench");
    expect(within(bench).getByRole("group", { name: "WR bench" })).toHaveTextContent("Wide Wendy");
    expect(within(screen.getByRole("region", { name: "Injured reserve" })).getByText("Hurt Harry")).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Taxi squad" })).getByText("Rookie Ron")).toBeInTheDocument();
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("tab", { name: "Trades" }));
    expect(screen.getByRole("button", { name: "Make an offer to Rivals" })).toBeEnabled();
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("tab", { name: "History" }));
    expect(await screen.findByRole("region", { name: "Record by season" })).toBeInTheDocument();
    expect(mocked.getSimTeamHistory).toHaveBeenCalledWith("g1", "7");
    expect(within(screen.getByRole("region", { name: "League draft class" })).getByText("Otis Opp")).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Transactions" })).getByText("Claimed Wally Wire, dropped Hurt Harry")).toBeInTheDocument();
  });

  it("shows coming-soon when the flag is off (404)", async () => {
    mocked.getSimGameOptions.mockRejectedValue(Object.assign(new Error("Not Found"), { status: 404 }));
    render(<SimGameContent />);
    expect(await screen.findByText("Fantasy Sim is coming soon")).toBeInTheDocument();
  });

  it("shows a retryable unavailable state when storage is missing", async () => {
    mocked.getSimGameOptions.mockResolvedValue({ ok: true, reason: "sim_storage_unavailable", is_premium: true, upsell: null, preview: null });
    render(<SimGameContent />);
    expect(await screen.findByText("Fantasy Sim is temporarily unavailable")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("an unexpected load failure uses the shared ErrorState with retry", async () => {
    mocked.getSimGameOptions.mockRejectedValue(new Error("Could not reach the server."));
    render(<SimGameContent />);
    expect(await screen.findByText("Something went wrong")).toBeInTheDocument();
    mocked.getSimGameOptions.mockResolvedValue(options());
    mocked.listSimGames.mockResolvedValue({ ok: true, reason: "", games: [] });
    fireEvent.click(screen.getByRole("button", { name: /Try again/ }));
    expect(await screen.findByText("Be the GM. Win the season.")).toBeInTheDocument();
  });

  it("blocks a second game for a Free account and offers Pro", async () => {
    mocked.getSimGameOptions.mockResolvedValue(options({ is_premium: false, max_games: 1, preview: { weeks_left: 3, paywall_week: 4, paywalled: false } }));
    mocked.listSimGames.mockResolvedValue({ ok: true, reason: "", games: [lite(game())] });
    render(<SimGameContent />);
    expect(await screen.findByTestId("new-game-block")).toHaveTextContent("Free includes 1 saved game");
    expect(screen.getByRole("button", { name: "New game" })).toBeDisabled();
    expect(screen.getByRole("link", { name: "Go Pro" })).toHaveAttribute("href", "/premium");
    expect(screen.getByTestId("sim-preview-line")).toHaveTextContent("3 weeks left");
  });

  it("limit reached: names the count, offers Manage, and deleting from the hub frees New game immediately", async () => {
    const g2 = { ...lite(game({ id: "g2" })), status: "complete" as const, grade_letter: "B+" };
    mocked.getSimGameOptions.mockResolvedValue(options({ max_games: 2 }));
    mocked.listSimGames.mockResolvedValue({ ok: true, reason: "", games: [lite(game()), g2] });
    mocked.deleteSimGame.mockResolvedValue({ ok: true, reason: "" });
    render(<SimGameContent />);
    expect(await screen.findByTestId("new-game-block")).toHaveTextContent("You have 2 of 2 saved games");
    expect(screen.getByRole("button", { name: "Manage games / delete one" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "New game" })).toBeDisabled();
    fireEvent.click(screen.getByRole("button", { name: /Delete game: Finished/ }));
    expect(screen.getByRole("group", { name: /Delete this game\?.*can't be undone/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Keep" })).toHaveFocus();
    mocked.listSimGames.mockResolvedValue({ ok: true, reason: "", games: [lite(game())] });
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(mocked.deleteSimGame).toHaveBeenCalledWith("g2"));
    await waitFor(() => expect(screen.queryByTestId("new-game-block")).toBeNull());
    expect(screen.getByRole("button", { name: "New game" })).toBeEnabled();
    expect(screen.queryByRole("button", { name: /Delete game: Finished/ })).toBeNull();
  });

  it("a 503 on hub delete keeps the game and shows a busy notice", async () => {
    mocked.listSimGames.mockResolvedValue({ ok: true, reason: "", games: [lite(game())] });
    mocked.deleteSimGame.mockRejectedValue(Object.assign(new Error("busy"), { status: 503 }));
    render(<SimGameContent />);
    fireEvent.click(await screen.findByRole("button", { name: /Delete game: Week/ }));
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(await screen.findByText(/simulator is busy/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Open game/ })).toBeInTheDocument();
  });

  it("a 404 on hub delete drops the already-gone game", async () => {
    mocked.listSimGames.mockResolvedValue({ ok: true, reason: "", games: [lite(game())] });
    mocked.deleteSimGame.mockRejectedValue(Object.assign(new Error("nf"), { status: 404 }));
    render(<SimGameContent />);
    fireEvent.click(await screen.findByRole("button", { name: /Delete game: Week/ }));
    mocked.listSimGames.mockResolvedValue({ ok: true, reason: "", games: [] });
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(await screen.findByText("No games yet")).toBeInTheDocument();
  });

  it("Free past week 3: Advance becomes Go Pro, never calls the API, and reads still render", async () => {
    mocked.getSimGameOptions.mockResolvedValue(options({ is_premium: false, max_games: 1, preview: { weeks_left: 0, paywall_week: 4, paywalled: true } }));
    mocked.listSimGames.mockResolvedValue({ ok: true, reason: "", games: [lite(game())] });
    mocked.getSimGame.mockResolvedValue({ ok: true, reason: "", game: game(), preview: { weeks_left: 0, paywall_week: 4, paywalled: true } });
    render(<SimGameContent />);
    await openFirstGame();
    expect(await screen.findByRole("link", { name: "Go Pro to continue" })).toHaveAttribute("href", "/premium");
    expect(screen.queryByRole("button", { name: /Advance to week/ })).not.toBeInTheDocument();
    await openTeamTab();
    expect(await screen.findByText("Quinn Back")).toBeInTheDocument();
    expect(screen.getByTestId("sim-preview-line")).toHaveTextContent("paused at week 4");
    expect(mocked.advanceSimGame).not.toHaveBeenCalled();
  });

  it("a premium_required answer to a write shows the upsell over the still-visible game", async () => {
    mocked.getSimGameOptions.mockResolvedValue(options({ is_premium: false, max_games: 1, preview: { weeks_left: 1, paywall_week: 4, paywalled: false } }));
    mocked.listSimGames.mockResolvedValue({ ok: true, reason: "", games: [lite(game({ week: 3 }))] });
    mocked.getSimGame.mockResolvedValue({ ok: true, reason: "", game: game({ week: 3 }), preview: { weeks_left: 1, paywall_week: 4, paywalled: false } });
    mocked.advanceSimGame.mockResolvedValue(premiumBody);
    render(<SimGameContent />);
    await openFirstGame();
    fireEvent.click(await screen.findByRole("button", { name: /Advance to week 4/ }));
    expect(await screen.findByTestId("sim-paywall")).toHaveTextContent("Pro unlocks the rest of the season.");
    expect(mocked.advanceSimGame).toHaveBeenCalledWith("g1", 3);
    expect(screen.getByTestId("sim-home")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Keep looking around" }));
    expect(screen.queryByTestId("sim-paywall")).not.toBeInTheDocument();
  });

  it("an over-limit roster blocks Advance before any call", async () => {
    const over = game({ pending: { claims: 0, inbox: 0, lineup_warnings: 0, roster_size: 18, roster_limit: 16, cuts_needed: 2 } });
    mocked.listSimGames.mockResolvedValue({ ok: true, reason: "", games: [lite(over)] });
    mocked.getSimGame.mockResolvedValue({ ok: true, reason: "", game: over });
    render(<SimGameContent />);
    await openFirstGame();
    fireEvent.click(await screen.findByRole("button", { name: /Advance to week 5/ }));
    expect(await screen.findAllByText(/Cut 2 players/)).not.toHaveLength(0);
    expect(mocked.advanceSimGame).not.toHaveBeenCalled();
  });

  it("the bottom bar keeps Advance reachable from every tab and warns (not blocks) on an empty slot and confirms", async () => {
    mocked.listSimGames.mockResolvedValue({ ok: true, reason: "", games: [lite(game())] });
    mocked.getSimLineup.mockResolvedValue({ ...lineup, slots: [{ slot: "QB", player: player("1", "QB", "Quinn Back") }, { slot: "RB", player: null }] });
    render(<SimGameContent />);
    await openFirstGame();
    const bar = await screen.findByTestId("sim-action-bar");
    expect(await screen.findByTestId("sim-advance-warning")).toHaveTextContent("RB will score 0");
    const advanceBtn = screen.getByRole("button", { name: /Advance to week 5/ });
    expect(advanceBtn).not.toBeDisabled();
    fireEvent.click(advanceBtn);
    expect(await screen.findByTestId("sim-advance-confirm")).toHaveTextContent("RB is empty and will score 0");
    expect(mocked.advanceSimGame).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(bar).toHaveTextContent("Wk 4");
    await openTeamTab();
    expect(screen.getByTestId("sim-action-bar")).toBeInTheDocument();
  });

  it("Advance plays the week, shows the recap, then returns to the team", async () => {
    mocked.listSimGames.mockResolvedValue({ ok: true, reason: "", games: [lite(game())] });
    mocked.advanceSimGame.mockResolvedValue({
      ok: true, reason: "", is_premium: true, game: game({ week: 5 }),
      recap: { week: 4, kind: "regular", round: null, your_game: { opponent_id: "7", opponent_name: "Rivals", your_pts: 128.4, opp_pts: 109.7, result: "win", starters: [] }, scores: [], season_complete: false, champion: null, next_week: 5 },
    });
    render(<SimGameContent />);
    await openFirstGame();
    fireEvent.click(await screen.findByRole("button", { name: /Advance to week 5/ }));
    // The recap is a full-screen story: Result first, Next week last (this recap has no starters, scores or injuries).
    const story = await screen.findByTestId("week-recap-story");
    expect(story).toHaveAttribute("aria-label", "Week 4 recap");
    expect(screen.getByText("Win")).toBeInTheDocument();
    expect(screen.getByText("Won by 18.7")).toBeInTheDocument();
    expect(mocked.advanceSimGame).toHaveBeenCalledWith("g1", 4);
    fireEvent.keyDown(story, { key: "ArrowRight" });
    fireEvent.click(screen.getByRole("button", { name: "Back to your team" }));
    await waitFor(() => expect(screen.queryByTestId("week-recap-story")).not.toBeInTheDocument());
    expect(screen.getByTestId("game-heading")).toHaveTextContent("Week 5 of 14");
  });

  const simToSummary = {
    weeks: [
      { week: 4, kind: "regular", round: null, result: "w", your_pts: 128.4, opp_pts: 109.7, opponent: "Rivals", auto_filled: [] },
      { week: 5, kind: "regular", round: null, result: "l", your_pts: 90.1, opp_pts: 101.3, opponent: "Rats", auto_filled: ["WR"] },
    ],
    record: { before: "2-1", after: "3-2" }, rank: { before: 4, after: 5 }, pf: 218.5,
    injuries: [{ week: 5, player: { id: "9", name: "Hurt Harry", pos: "RB" }, weeks: 3 }], claims: [], ai_trades: 2,
    standings: [{ rank: 1, team_id: "7", name: "Rivals", is_you: false, wins: 4, losses: 1, ties: 0, pf: 500, pa: 400, playoff_status: "in" }], champion: null, season_complete: false,
  };

  it("Sim to... offers the stage's milestones, runs one request with the auto-set toggle, and shows a compact summary with undo", async () => {
    mocked.listSimGames.mockResolvedValue({ ok: true, reason: "", games: [lite(game())] });
    mocked.getSimToOptions.mockResolvedValue({ ok: true, reason: "", options: [{ id: "weeks", weeks: 1, label: "Next week" }, { id: "trade_deadline", label: "Trade deadline (week 10)" }, { id: "season_end", label: "Through the playoffs" }] });
    mocked.simToGame.mockResolvedValue({ ok: true, reason: "", is_premium: true, target: "trade_deadline", weeks_played: 2, stopped: { code: "starter_out", week: 6, message: "Stopped at Week 6: your QB is out: Quinn Back (QB).", fix: "lineup" }, from_seq: 41, to_seq: 80, summary: simToSummary, recap: null, game: game({ week: 6 }) });
    mocked.undoSimTo.mockResolvedValue({ ok: true, reason: "", undone: true, game: game({ week: 4 }) });
    render(<SimGameContent />);
    await openFirstGame();
    fireEvent.click(await screen.findByTestId("sim-to-button"));
    expect(await screen.findByRole("button", { name: "Trade deadline (week 10)" })).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "Auto-set my lineup each week" })).not.toBeChecked(); // off by default
    fireEvent.click(screen.getByRole("checkbox", { name: "Auto-set my lineup each week" }));
    fireEvent.click(screen.getByRole("button", { name: "Trade deadline (week 10)" }));
    const result = await screen.findByTestId("sim-to-result");
    expect(mocked.simToGame).toHaveBeenCalledTimes(1);
    expect(mocked.simToGame).toHaveBeenCalledWith("g1", { target: "trade_deadline", weeks: undefined, auto_set: true, force_first: undefined });
    expect(result).toHaveTextContent("Simmed 2 weeks (Weeks 4-5)");
    expect(result).toHaveTextContent("2-1 to 3-2 · #4 to #5");
    expect(screen.getByTestId("sim-to-stop")).toHaveTextContent("Stopped at Week 6: your QB is out");
    expect(within(result).getByRole("button", { name: "Fix lineup" })).toBeInTheDocument();
    expect(within(result).queryByRole("button", { name: "Sim anyway" })).toBeNull(); // weeks were played: nothing to force
    expect(result).toHaveTextContent("Hurt Harry (RB), out 3 weeks");
    expect(result).toHaveTextContent("W 128.4-109.7 vs Rivals");
    expect(screen.getByTestId("game-heading")).toHaveTextContent("Week 6 of 14");
    // undo takes the whole run back
    fireEvent.click(within(result).getByRole("button", { name: "Undo this sim" }));
    fireEvent.click(await within(result).findByRole("button", { name: /Tap again/ }));
    await waitFor(() => expect(mocked.undoSimTo).toHaveBeenCalledWith("g1", 41));
    await waitFor(() => expect(screen.queryByTestId("sim-to-result")).not.toBeInTheDocument());
  });

  it("a stop before any week is played shows the reason, a fix button to the right tab, and Sim anyway forces the first week", async () => {
    mocked.listSimGames.mockResolvedValue({ ok: true, reason: "", games: [lite(game())] });
    mocked.getSimToOptions.mockResolvedValue({ ok: true, reason: "", options: [{ id: "weeks", weeks: 1, label: "Next week" }] });
    const stop = { code: "trade_offers", week: 4, message: "Stopped at Week 4: 2 trade offers will expire this week.", fix: "inbox", count: 2 };
    mocked.simToGame.mockResolvedValueOnce({ ok: true, reason: "", is_premium: true, target: "weeks", weeks_played: 0, stopped: stop, from_seq: 40, to_seq: 40, summary: null, recap: null, game: game() });
    mocked.simToGame.mockResolvedValueOnce({ ok: true, reason: "", is_premium: true, target: "weeks", weeks_played: 1, stopped: null, from_seq: 40, to_seq: 70, summary: { ...simToSummary, weeks: [simToSummary.weeks[0]] }, recap: null, game: game({ week: 5 }) });
    render(<SimGameContent />);
    await openFirstGame();
    fireEvent.click(await screen.findByTestId("sim-to-button"));
    fireEvent.click(await screen.findByRole("button", { name: "Next week" }));
    const result = await screen.findByTestId("sim-to-result");
    expect(result).toHaveTextContent("Nothing simulated");
    expect(screen.getByTestId("sim-to-stop")).toHaveTextContent("Stopped at Week 4: 2 trade offers will expire this week.");
    expect(within(result).queryByRole("button", { name: "Undo this sim" })).toBeNull();
    fireEvent.click(within(result).getByRole("button", { name: "Sim anyway" }));
    await waitFor(() => expect(mocked.simToGame).toHaveBeenCalledTimes(2));
    expect(mocked.simToGame).toHaveBeenLastCalledWith("g1", { target: "weeks", weeks: 1, auto_set: false, force_first: true });
    expect(await screen.findByTestId("sim-to-result")).toHaveTextContent("Simmed Week 4");
  });

  it("a raced write (409) reloads the game and says so instead of failing", async () => {
    mocked.listSimGames.mockResolvedValue({ ok: true, reason: "", games: [lite(game())] });
    mocked.advanceSimGame.mockRejectedValue(Object.assign(new Error("Request failed with status 409."), { status: 409 }));
    render(<SimGameContent />);
    await openFirstGame();
    fireEvent.click(await screen.findByRole("button", { name: /Advance to week 5/ }));
    expect(await screen.findByText(/game changed somewhere else/)).toBeInTheDocument();
    await waitFor(() => expect(mocked.getSimGame.mock.calls.length).toBeGreaterThan(1));
  });

  it("drafts from the board when on the clock and shows the recap when the draft ends", async () => {
    const drafting = game({ status: "drafting", week: 0, phase: "draft", this_week: null, pending: null, you: { team_id: "3", name: "My Team", wins: 0, losses: 0, ties: 0, pf: 0, pa: 0, rank: null, seed: null } });
    const star = player("10", "RB", "Rory Runner");
    const draftState = {
      status: "in_progress" as const, pick_no: 3, round: 1, total_picks: 168, on_the_clock: { team_id: "3", name: "My Team", is_you: true },
      your_pick_numbers: [3], picks_until_you: 0, queue: [], your_roster: [], picks: [], teams: [{ team_id: "3", name: "My Team", is_you: true }],
    };
    mocked.listSimGames.mockResolvedValue({ ok: true, reason: "", games: [lite(drafting)] });
    mocked.getSimGame.mockResolvedValue({ ok: true, reason: "", game: drafting });
    mocked.getSimDraft.mockResolvedValue({ ok: true, reason: "", draft: draftState, available: { items: [], total: 0, page: 1, page_size: 1 }, hint: { player: star, why: "Best available for your need: RB" } });
    mocked.getSimGamePlayers.mockResolvedValue({ ok: true, reason: "", items: [star], total: 1, page: 1, page_size: 40 });
    mocked.simDraftPick.mockResolvedValue({
      ok: true, reason: "", picks: [{ pick_no: 3, round: 1, team_id: "3", player: star, adp: 3, value_over_adp: 2, auto: false }], draft: { ...draftState, status: "complete", on_the_clock: null },
      completed: true, recap: { teams: [{ team_id: "3", name: "My Team", grade: "A-", starter_projection: 130, is_you: true }], your_team: { team_id: "3", name: "My Team", grade: "A-", starter_projection: 130, best_pick: { player: star }, worst_pick: null } },
      game: game({ week: 1 }),
    });
    render(<SimGameContent />);
    await openFirstGame();
    expect(await screen.findByText("You are on the clock.")).toBeInTheDocument();
    const draftButton = await screen.findByRole("button", { name: "Draft Rory Runner" });
    // A double tap in the same frame still submits once, carrying the pick the client believes is on the clock.
    fireEvent.click(draftButton);
    fireEvent.click(draftButton);
    expect(await screen.findByTestId("draft-recap")).toHaveTextContent("Draft grade A-");
    expect(mocked.simDraftPick).toHaveBeenCalledTimes(1);
    expect(mocked.simDraftPick).toHaveBeenCalledWith("g1", "10", 3);
    fireEvent.click(screen.getByRole("button", { name: "Start the season" }));
    expect(await screen.findByTestId("game-heading")).toHaveTextContent("Week 1 of 14");
  });

  describe("new game setup", () => {
    const setupOptions = () =>
      options({
        options: {
          mode: { values: ["redraft"], default: "redraft" },
          teams: { values: [8, 10, 12, 14], default: 12 },
          scoring: { values: ["ppr", "half", "std"], default: "half" },
          te_premium: { values: [0, 0.5, 1], default: 0 },
          superflex: { default: false },
          include_k: { default: true },
          include_def: { default: false },
          bench: { min: 4, max: 10, default: 8 },
          difficulty: { values: ["easy", "normal", "hard"], default: "normal" },
          user_slot: { min: 1, max: 14, default: null },
          auto_lineup: { default: false },
          team_names: { values: ["Gridiron Ghosts", "Blitz Brigade"], max_length: 40 },
        },
        layout: { base_slots: ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX"], draft_spare_spots: 2 },
        start_modes: [{ id: "fresh", available: true }, { id: "league", available: true }, { id: "season_start", available: false, reason: "no_roster_history" }],
      });

    async function openSetup() {
      mocked.getSimGameOptions.mockResolvedValue(setupOptions());
      mocked.listSimGames.mockResolvedValue({ ok: true, reason: "", games: [] });
      render(<SimGameContent />);
      fireEvent.click(await screen.findByRole("button", { name: "New game" }));
      await screen.findByText("Quick start is 12 teams, half PPR and a standard lineup. You can change nothing after the game starts.");
    }

    it("quick start: advanced options start collapsed and the defaults are 12 teams, half PPR, standard lineup", async () => {
      await openSetup();
      expect(screen.getByTestId("sim-advanced")).not.toHaveAttribute("open");
      expect(screen.getByTestId("sim-setup-summary")).toHaveTextContent("12 teams, 14-round snake draft. Starters: QB, RB, RB, WR, WR, TE, FLEX, K. Roster 16.");
      mocked.createSimGame.mockResolvedValue({ ok: true, reason: "premium_required", is_premium: true });
      fireEvent.click(screen.getByRole("button", { name: "Start the draft" }));
      await waitFor(() => expect(mocked.createSimGame).toHaveBeenCalled());
      expect(mocked.createSimGame.mock.calls[0][0]).toEqual({
        difficulty: "normal", auto_lineup: false, tiebreaker: "points_for", random_team_name: true, teams: 12, scoring: "half", te_premium: 0, superflex: false,
        include_k: true, include_def: false, bench: 8, mode: "redraft", user_slot: null,
      });
    });

    it("advanced options change the league and the derived draft length", async () => {
      await openSetup();
      fireEvent.click(screen.getByRole("switch", { name: "Superflex" }));
      fireEvent.click(screen.getByRole("switch", { name: "Defense (DEF)" }));
      fireEvent.click(screen.getByRole("tab", { name: "14 teams" }));
      fireEvent.click(screen.getByRole("tab", { name: "Standard" }));
      expect(screen.getByTestId("sim-setup-summary")).toHaveTextContent("14 teams, 16-round snake draft. Starters: QB, RB, RB, WR, WR, TE, FLEX, SUPER_FLEX, K, DEF. Roster 18.");
      expect(screen.getByText(/Advanced options \(4 changed\)/)).toBeInTheDocument();
      mocked.createSimGame.mockResolvedValue({ ok: true, reason: "premium_required", is_premium: true });
      fireEvent.click(screen.getByRole("button", { name: "Start the draft" }));
      await waitFor(() => expect(mocked.createSimGame).toHaveBeenCalled());
      expect(mocked.createSimGame.mock.calls[0][0]).toMatchObject({ teams: 14, scoring: "std", superflex: true, include_def: true, include_k: true });
    });

    it("start from one of my leagues: Sleeper leagues only, hides the league-shape options, sends league_id", async () => {
      await openSetup();
      fireEvent.click(screen.getByRole("tab", { name: "My league" }));
      // The league decides size, scoring and lineup; only the reserve squads stay in Advanced.
      expect(screen.queryByRole("tablist", { name: "League size" })).not.toBeInTheDocument();
      expect(screen.queryByRole("tablist", { name: "Scoring" })).not.toBeInTheDocument();
      const pick = await screen.findByRole("combobox", { name: "League to start from" });
      await screen.findByRole("option", { name: "Dynasty Dogs" });
      expect(screen.queryByRole("option", { name: "ESPN Thing" })).not.toBeInTheDocument();
      const submit = screen.getByRole("button", { name: "Start the season" });
      expect(submit).toBeDisabled();
      mocked.getSimLeagueTeams.mockResolvedValue({
        ok: true, reason: "", league_id: "111", you_roster_id: "2",
        teams: [
          { roster_id: "1", team_name: "Alpha Squad", owner_name: "bob", wins: 5, losses: 2, ties: 0, points_for: 700, rank: 1, is_you: false },
          { roster_id: "2", team_name: "The Dude's Team \u{1F3C8}", owner_name: "dude", wins: 3, losses: 4, ties: 0, points_for: 600, rank: 4, is_you: true },
        ],
      });
      fireEvent.change(pick, { target: { value: "111" } });
      const teamPick = (await screen.findByRole("combobox", { name: "Your team in this league" })) as HTMLSelectElement;
      await waitFor(() => expect(teamPick.value).toBe("2"));
      expect(screen.queryByRole("textbox", { name: /team name/i })).not.toBeInTheDocument();
      expect(submit).not.toBeDisabled();
      mocked.createSimGame.mockResolvedValue({ ok: true, reason: "premium_required", is_premium: true });
      fireEvent.click(submit);
      await waitFor(() => expect(mocked.createSimGame).toHaveBeenCalled());
      expect(mocked.createSimGame.mock.calls[0][0]).toEqual({ difficulty: "normal", auto_lineup: false, tiebreaker: "points_for", start: "league", league_id: "111", roster_id: "2" });
    });

    it("start from a league: no auto-match means the player must pick a team; ESPN-style errors are explained", async () => {
      await openSetup();
      fireEvent.click(screen.getByRole("tab", { name: "My league" }));
      const pick = await screen.findByRole("combobox", { name: "League to start from" });
      await screen.findByRole("option", { name: "Dynasty Dogs" });
      mocked.getSimLeagueTeams.mockResolvedValue({
        ok: true, reason: "", league_id: "111", you_roster_id: null,
        teams: [{ roster_id: "1", team_name: "Alpha Squad", owner_name: "bob", wins: 0, losses: 0, ties: 0, points_for: 0, rank: 1, is_you: false }],
      });
      fireEvent.change(pick, { target: { value: "111" } });
      const teamPick = (await screen.findByRole("combobox", { name: "Your team in this league" })) as HTMLSelectElement;
      await screen.findByRole("option", { name: /Alpha Squad/ });
      expect(teamPick.value).toBe("");
      expect(screen.getByRole("button", { name: "Start the season" })).toBeDisabled();
      fireEvent.change(teamPick, { target: { value: "1" } });
      expect(screen.getByRole("button", { name: "Start the season" })).not.toBeDisabled();
    });

    it("start from a league: a league the game cannot read shows why and blocks starting", async () => {
      await openSetup();
      fireEvent.click(screen.getByRole("tab", { name: "My league" }));
      const pick = await screen.findByRole("combobox", { name: "League to start from" });
      await screen.findByRole("option", { name: "Dynasty Dogs" });
      mocked.getSimLeagueTeams.mockResolvedValue({ ok: true, reason: "league_platform_unsupported" });
      fireEvent.change(pick, { target: { value: "111" } });
      await screen.findByText("Only Sleeper leagues can start a game for now.");
      expect(screen.getByRole("button", { name: "Start the season" })).toBeDisabled();
    });

    it("fresh league: team name is a preset picker with Random, Custom reveals a text input", async () => {
      await openSetup();
      const names = screen.getByRole("combobox", { name: "Your team name" });
      expect(Array.from((names as HTMLSelectElement).options).map((o) => o.text)).toEqual(["Random", "Gridiron Ghosts", "Blitz Brigade", "Custom name..."]);
      fireEvent.change(names, { target: { value: "__custom__" } });
      fireEvent.change(screen.getByRole("textbox", { name: "Custom team name" }), { target: { value: "  O'Neil's  Crew \u{1F3C8} " } });
      mocked.createSimGame.mockResolvedValue({ ok: true, reason: "premium_required", is_premium: true });
      fireEvent.click(screen.getByRole("button", { name: "Start the draft" }));
      await waitFor(() => expect(mocked.createSimGame).toHaveBeenCalled());
      expect(mocked.createSimGame.mock.calls[0][0]).toMatchObject({ team_name: "O'Neil's Crew \u{1F3C8}" });
      expect(mocked.createSimGame.mock.calls[0][0]).not.toHaveProperty("random_team_name");
    });

    it("hides the my-league choice when the server says it is unavailable", async () => {
      mocked.getSimGameOptions.mockResolvedValue({ ...setupOptions(), start_modes: [{ id: "fresh", available: true }, { id: "league", available: false }] });
      mocked.listSimGames.mockResolvedValue({ ok: true, reason: "", games: [] });
      render(<SimGameContent />);
      fireEvent.click(await screen.findByRole("button", { name: "New game" }));
      await screen.findByText(/Quick start is/);
      expect(screen.queryByRole("tab", { name: "My league" })).not.toBeInTheDocument();
    });
  });
});
