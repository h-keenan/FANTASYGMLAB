import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SimGameContent } from "./SimGameContent";
import { api } from "@/lib/api";
import type { SimGame, SimGameOptionsResponse, SimGamePlayer, SimLineupResponse, SimOffseason } from "@/lib/simGame";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/lib/supabase", () => ({
  supabase: { from: () => ({ select: () => Promise.resolve({ data: [{ league_id: "111", league_name: "Dynasty Dogs" }], error: null }) }) },
}));
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  const names = [
    "getSimGameOptions", "getSimLeagueTeams", "listSimGames", "createSimGame", "getSimGame", "getSimGamePlayers", "getSimGameTeam", "getSimHome",
    "getSimLineup", "putSimLineup", "autoSimLineup", "cutSimPlayer", "previewSimTrade", "sendSimTrade", "getSimInbox", "getSimLeague", "getSimLeagueRosters", "getSimGameResult",
    "getSimPicks", "moveSimPlayer", "getSimOffseason", "startSimRookieDraft", "pickSimRookie", "autoSimRookieDraft", "startSimSeason", "getSimDynasty",
  ];
  return { ...actual, api: { ...actual.api, ...Object.fromEntries(names.map((n) => [n, vi.fn()])) } };
});
const mocked = api as unknown as Record<string, ReturnType<typeof vi.fn>>;

const player = (id: string, pos: SimGamePlayer["pos"], name: string, over: Partial<SimGamePlayer> = {}): SimGamePlayer => ({
  id, name, pos, team: "KC", age: 22, adp: 5, value: 80, projection: 14.2, floor: 7, ceiling: 24, status: "healthy", out_weeks: 0, bye_week: 9,
  owner: { type: "you" }, kind: "player", squad: "roster", taxi_eligible: true, rookie: false, ...over,
});

const SETTINGS = {
  teams: 12, scoring: "ppr", difficulty: "normal", regular_weeks: 14, playoff_teams: 6, playoff_weeks: 3, trade_deadline_week: 10, roster_limit: 16, rounds: 14,
  slots: ["QB", "RB", "WR", "TE", "FLEX"], user_slot: 3, auto_lineup: false, mode: "dynasty", seasons: 5, rookie_rounds: 4, reserve_v: 1, ir_slots: 2, taxi_slots: 4, taxi_years: 2,
} as SimGame["settings"];

function game(over: Partial<SimGame> = {}): SimGame {
  return {
    id: "g1", status: "in_season", week: 4, phase: "regular_season", round: null, seed: 1, engine_version: "game-1.2.0", settings: SETTINGS,
    you: { team_id: "3", name: "My Team", wins: 2, losses: 1, ties: 0, pf: 361.4, pa: 330.2, rank: 4, seed: null },
    this_week: null, pending: { claims: 0, inbox: 0, lineup_warnings: 0, roster_size: 16, roster_limit: 16, cuts_needed: 0 },
    can_trade: true, trade_deadline_week: 10, grade_letter: null, created_at: "", updated_at: "",
    dynasty: { season_no: 2, seasons: 5, year: 2027, stage: null, picks_held: 6, titles: 1, last_season: false }, ...over,
  };
}
const lite = (g: SimGame) => ({ id: g.id, seed: 1, engine_version: "x", settings: g.settings, status: g.status, current_week: g.week, difficulty: "normal" as const, grade_letter: null, event_count: 3, created_at: "", updated_at: "" });

const opts = (): SimGameOptionsResponse => ({
  ok: true, reason: "", is_premium: true, upsell: null, preview: null, max_games: 3,
  options: {
    mode: { values: ["redraft", "dynasty"], default: "redraft" },
    teams: { values: [8, 12], default: 12 }, scoring: { values: ["ppr", "half", "std"], default: "half" }, difficulty: { values: ["easy", "normal", "hard"], default: "normal" },
    user_slot: { min: 1, max: 12, default: null }, auto_lineup: { default: false },
    seasons: { values: [3, 4, 5], default: 5 }, rookie_rounds: { values: [2, 3, 4, 5], default: 4 },
    ir_slots: { min: 0, max: 4, default: 2 }, taxi_slots: { min: 0, max: 8, default: 0, default_dynasty: 4 }, taxi_years: { values: [1, 2, 3, 4], default: 2 },
  },
  layout: { base_slots: ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX"], draft_spare_spots: 2 },
  start_modes: [{ id: "fresh", available: true }, { id: "league", available: true }],
});

async function openGame() {
  fireEvent.click(await screen.findByRole("button", { name: /Open game/ }));
}

beforeEach(() => {
  vi.resetAllMocks();
  mocked.getSimGameOptions.mockResolvedValue(opts());
  mocked.getSimGamePlayers.mockResolvedValue({ ok: true, reason: "", items: [], total: 0, page: 1, page_size: 40 });
  mocked.getSimGameTeam.mockResolvedValue({ ok: true, reason: "", team_id: "3", players: [] });
  mocked.getSimPicks.mockResolvedValue({ ok: true, reason: "", enabled: true, draft_year: 2027, rounds: 4, years: 3, you: [], teams: [] });
});

describe("dynasty setup", () => {
  async function openSetup() {
    mocked.listSimGames.mockResolvedValue({ ok: true, reason: "", games: [] });
    render(<SimGameContent />);
    fireEvent.click(await screen.findByRole("button", { name: "New game" }));
    await screen.findByTestId("sim-setup-hero");
  }

  it("Customize picks Dynasty, seasons and rookie rounds, and sends them", async () => {
    await openSetup();
    fireEvent.click(screen.getByRole("tab", { name: "Customize" }));
    expect(screen.queryByRole("tablist", { name: "Seasons" })).not.toBeInTheDocument();
    fireEvent.click(within(screen.getByRole("tablist", { name: "Game mode" })).getByRole("tab", { name: "Dynasty" }));
    expect(within(screen.getByRole("tablist", { name: "Seasons" })).getByRole("tab", { name: "5" })).toHaveAttribute("aria-selected", "true");
    fireEvent.click(within(screen.getByRole("tablist", { name: "Seasons" })).getByRole("tab", { name: "3" }));
    fireEvent.click(within(screen.getByRole("tablist", { name: "Rookie draft rounds" })).getByRole("tab", { name: "2" }));
    expect(within(screen.getByRole("tablist", { name: "Taxi slots" })).getByRole("tab", { name: "Default (4)" })).toBeInTheDocument();
    fireEvent.click(within(screen.getByRole("tablist", { name: "IR slots" })).getByRole("tab", { name: "1" }));
    expect(screen.getByTestId("sim-setup-summary")).toHaveTextContent("Dynasty: up to 3 seasons");
    mocked.createSimGame.mockResolvedValue({ ok: true, reason: "premium_required", is_premium: true });
    fireEvent.click(screen.getByRole("button", { name: "Start the draft" }));
    await waitFor(() => expect(mocked.createSimGame).toHaveBeenCalled());
    expect(mocked.createSimGame.mock.calls[0][0]).toMatchObject({ mode: "dynasty", seasons: 3, rookie_rounds: 2, ir_slots: 1 });
    expect(mocked.createSimGame.mock.calls[0][0]).not.toHaveProperty("taxi_slots");
  });

  it("a league import as dynasty carries mode and says what comes along", async () => {
    await openSetup();
    fireEvent.click(screen.getByRole("tab", { name: "My league" }));
    fireEvent.click(screen.getByRole("tab", { name: "Customize" }));
    fireEvent.click(within(screen.getByRole("tablist", { name: "Game mode" })).getByRole("tab", { name: "Dynasty" }));
    expect(screen.getByTestId("sim-dynasty-note")).toHaveTextContent("picks, taxi squad and IR");
    mocked.getSimLeagueTeams.mockResolvedValue({ ok: true, reason: "", league_id: "111", you_roster_id: "2", teams: [{ roster_id: "2", team_name: "Me", owner_name: "me", wins: 0, losses: 0, ties: 0, points_for: 0, rank: 1, is_you: true }] });
    fireEvent.change(await screen.findByRole("combobox", { name: "League to start from" }), { target: { value: "111" } });
    const submit = screen.getByRole("button", { name: "Start the season" });
    await waitFor(() => expect(submit).not.toBeDisabled());
    mocked.createSimGame.mockResolvedValue({ ok: true, reason: "premium_required", is_premium: true });
    fireEvent.click(submit);
    await waitFor(() => expect(mocked.createSimGame).toHaveBeenCalled());
    expect(mocked.createSimGame.mock.calls[0][0]).toMatchObject({ start: "league", league_id: "111", mode: "dynasty", seasons: 5, rookie_rounds: 4 });
  });
});

describe("IR and taxi on the Team tab", () => {
  const lineup: SimLineupResponse = {
    ok: true, reason: "", week: 4, slots: [{ slot: "QB", player: player("1", "QB", "Quinn Back") }],
    bench: [player("2", "RB", "Rookie Ray", { rookie: true }), player("3", "WR", "Hurt Hank", { status: "out", out_weeks: 3, taxi_eligible: false })],
    ir: [player("8", "TE", "Ivy Reserve", { squad: "ir", status: "out", out_weeks: 6 })], taxi: [],
    projected_total: 100, warnings: [], roster_size: 16, roster_limit: 16, opponent: null, locked: false,
    reserves: { enabled: true, ir_slots: 2, taxi_slots: 4, taxi_years: 2, ir_used: 1, taxi_used: 0 },
  };

  async function openTeam() {
    mocked.listSimGames.mockResolvedValue({ ok: true, reason: "", games: [lite(game())] });
    mocked.getSimGame.mockResolvedValue({ ok: true, reason: "", game: game() });
    mocked.getSimLineup.mockResolvedValue(lineup);
    mocked.getSimHome.mockResolvedValue({ ok: true, reason: "", week: 4, phase: "regular_season", matchup: null, checklist: [], inbox: { count: 0, open: true, items: [] }, waiver_suggestions: [], bye_alerts: [], injuries: [], hot_cold: { hot: [], cold: [], wire: [] }, standings: { rows: [], playoff_spots: 6, games_left: 10, your_rank: 1, margin: 0, in_playoffs: true }, league: { recent: [], spotlight: null } });
    render(<SimGameContent />);
    await openGame();
    fireEvent.click(await screen.findByRole("tab", { name: "Team" }));
    await screen.findByTestId("reserve-groups");
  }

  it("shows the summary line first, IR and taxi groups and the chips", async () => {
    await openTeam();
    expect(screen.getByTestId("reserve-summary")).toHaveTextContent("IR 1 of 2 · Taxi 0 of 4");
    expect(within(screen.getByTestId("reserve-ir")).getByText("Ivy Reserve")).toBeInTheDocument();
    expect(within(screen.getByTestId("reserve-ir")).getAllByText("IR").length).toBeGreaterThan(0);
    expect(screen.getByText("ROOKIE")).toBeInTheDocument();
    expect(screen.getAllByText("OUT 3 wks").length).toBeGreaterThan(0);
    // taxi is collapsed (empty), picks summary is collapsed
    expect(within(screen.getByTestId("reserve-taxi")).queryByText(/Nobody on the taxi squad/)).not.toBeInTheDocument();
    expect(screen.getByTestId("your-picks")).toBeInTheDocument();
  });

  it("the move menu disables what the rules forbid and moves a player with POST /roster/move", async () => {
    await openTeam();
    fireEvent.click(screen.getByRole("button", { name: "Move Rookie Ray to IR, taxi or roster" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByRole("button", { name: /^Move to IR/ })).toBeDisabled();
    // the reason is part of the disabled button, not a floating sentence
    expect(within(dialog).getByTestId("reserve-hint-ir")).toHaveTextContent("Move to IR · Not injured");
    expect(within(dialog).queryByRole("button", { name: "Close" })).toBeNull(); // the X and swipe close the sheet
    mocked.moveSimPlayer.mockResolvedValue({ ...lineup, ok: true, reason: "", bench: [lineup.bench![1]], taxi: [player("2", "RB", "Rookie Ray", { squad: "taxi", rookie: true })], reserves: { ...lineup.reserves!, taxi_used: 1 }, move: { pid: "2", src: "roster", dst: "taxi" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Move to taxi" }));
    await waitFor(() => expect(mocked.moveSimPlayer).toHaveBeenCalledWith("g1", { player_id: "2", to: "taxi" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(screen.getByTestId("reserve-summary")).toHaveTextContent("Taxi 1 of 4");
  });

  it("shows the backend reason inline when a move is refused", async () => {
    await openTeam();
    fireEvent.click(screen.getByRole("button", { name: "Move Rookie Ray to IR, taxi or roster" }));
    const dialog = await screen.findByRole("dialog");
    mocked.moveSimPlayer.mockResolvedValue({ ok: false, reason: "taxi_full", message: "Your taxi squad is full." });
    fireEvent.click(within(dialog).getByRole("button", { name: "Move to taxi" }));
    expect(await within(dialog).findByTestId("reserve-refusal")).toHaveTextContent("Your taxi squad is full.");
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("an injured bench player can go to IR and an IR player can be activated when there is room", async () => {
    await openTeam();
    fireEvent.click(screen.getByRole("button", { name: "Move Hurt Hank to IR, taxi or roster" }));
    expect(within(await screen.findByRole("dialog")).getByRole("button", { name: "Move to IR" })).toBeEnabled();
    fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: /^Close/ }));
    fireEvent.click(screen.getByRole("button", { name: "Move Ivy Reserve to IR, taxi or roster" }));
    // roster is 16 of 16, so activating is blocked with the reason beside it
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByRole("button", { name: /^Activate/ })).toBeDisabled();
    expect(within(dialog).getByTestId("reserve-hint-roster")).toHaveTextContent("Activate · Roster full");
  });
});

describe("offseason", () => {
  const archive = {
    season_no: 2, year: 2027, champion: { team_id: "7", name: "Rivals", is_you: false },
    you: { rank: 3, wins: 9, losses: 5, ties: 0, pf: 1500.5, seed: 3, playoff_result: "semifinal", made_playoffs: true, avg_age: 25.9, top_scorers: [{ id: "1", name: "Quinn Back", pos: "QB", pts: 320.1 }] },
  };
  const row = (n: number, mine: boolean) => ({ n, round: 1, pick: `pick:2028:1:${n}`, orig_team_id: String(n), orig_team_name: `Team ${n}`, team_id: mine ? "3" : String(n), team_name: mine ? "My Team" : `Team ${n}`, is_yours: mine, traded: false, made: null });
  const off = (over: Partial<SimOffseason> = {}): SimOffseason => ({
    stage: "review", year: 2028, season_no: 2, seasons: 5, last_season: archive as never,
    retired: [{ id: "r1", name: "Old Otto", pos: "QB", age: 39, market: 3, is_yours: true }, { id: "r2", name: "Gone Gus", pos: "RB", age: 33, market: 1, is_yours: false }],
    movers: [{ ...player("1", "QB", "Quinn Back"), age_before: 27, age_after: 28, mean_before: 18, mean_after: 17.1, delta: -0.9 }],
    your_picks_this_draft: [row(4, true)],
    draft: { round_count: 4, total: 48, pick_index: 0, order: [row(1, false), row(4, true)], on_clock: null, your_turn: false, available: [player("n1", "WR", "Rook Rookie", { rookie: true, owner: { type: "free_agent" } })], available_count: 1 },
    roster: { size: 18, limit: 16, cuts_needed: 2, ir: [], taxi: [], reserves: { enabled: true, ir_slots: 2, taxi_slots: 4, taxi_years: 2, ir_used: 0, taxi_used: 0 } },
    can_trade: true, next: "start_rookie_draft", picks_held: 5, ...over,
  } as SimOffseason);
  const og = () => game({ status: "offseason", phase: "offseason", week: 0, dynasty: { season_no: 2, seasons: 5, year: 2027, stage: "review", picks_held: 5, titles: 0, last_season: false } });

  async function openOffseason(o: SimOffseason) {
    mocked.listSimGames.mockResolvedValue({ ok: true, reason: "", games: [lite(og())] });
    mocked.getSimGame.mockResolvedValue({ ok: true, reason: "", game: og() });
    mocked.getSimOffseason.mockResolvedValue({ ok: true, reason: "", offseason: o });
    mocked.getSimDynasty.mockResolvedValue({ ok: true, reason: "", dynasty: { mode: "dynasty", seasons_total: 5, seasons_played: 2, start_year: 2026, complete: false, titles: 0, playoff_trips: 2, avg_finish: 2.5, wins: 20, losses: 8, best_season: null, by_year: [{ season_no: 1, year: 2026, rank: 2, record: "11-3", pf: 1600, playoff_result: "runner_up", champion: { team_id: "7", name: "Rivals", is_you: false }, avg_age: 26, top_scorers: [] }], picks_held: 5 } });
    render(<SimGameContent />);
    await openGame();
    await screen.findByTestId("offseason");
  }

  it("review: summary first, no Advance button, retirees, aging and the Start rookie draft button", async () => {
    await openOffseason(off());
    expect(screen.getByTestId("game-heading")).toHaveTextContent("Offseason");
    expect(screen.queryByRole("button", { name: /Advance/ })).not.toBeInTheDocument();
    expect(screen.getByTestId("dynasty-progress")).toHaveTextContent("S2 2027 (2 of 5)");
    expect(screen.getByTestId("off-last-season")).toHaveTextContent("9-5, 3rd");
    expect(screen.getByTestId("off-retired")).toHaveTextContent("2 retired, 1 yours");
    expect(screen.getByText("Old Otto")).toBeInTheDocument();
    expect(await screen.findByTestId("dynasty-strip")).toHaveTextContent("2026");
    expect(screen.getByTestId("mover")).toHaveTextContent("0.9");
    expect(screen.getByTestId("off-picks")).toHaveTextContent("Round 1, pick 4");
    mocked.getSimOffseason.mockResolvedValue({ ok: true, reason: "", offseason: off({ stage: "rookie_draft" }) });
    mocked.startSimRookieDraft.mockResolvedValue({ ok: true, reason: "", offseason: off({ stage: "rookie_draft" }), made: [] });
    fireEvent.click(screen.getByRole("button", { name: "Start rookie draft" }));
    await waitFor(() => expect(mocked.startSimRookieDraft).toHaveBeenCalledWith("g1"));
    expect(await screen.findByTestId("rookie-clock")).toBeInTheDocument();
  });

  it("rookie draft: on the clock banner, drafts a rookie with the pick call", async () => {
    const d = off({ stage: "rookie_draft" });
    d.draft = { ...d.draft, on_clock: row(4, true), your_turn: true, pick_index: 3 };
    await openOffseason(d);
    expect(screen.getByTestId("rookie-clock")).toHaveTextContent("You are on the clock");
    mocked.getSimOffseason.mockResolvedValue({ ok: true, reason: "", offseason: off({ stage: "cutdown" }) });
    mocked.pickSimRookie.mockResolvedValue({ ok: true, reason: "", offseason: off({ stage: "cutdown" }), made: [] });
    fireEvent.click(screen.getByRole("button", { name: "Draft Rook Rookie" }));
    await waitFor(() => expect(mocked.pickSimRookie).toHaveBeenCalledWith("g1", "n1"));
    expect(await screen.findByTestId("roster-check")).toHaveTextContent("Cut 2 players");
  });

  it("roster check: Start season is blocked until the cuts are made", async () => {
    mocked.getSimGameTeam.mockResolvedValue({ ok: true, reason: "", team_id: "3", players: [player("1", "QB", "Quinn Back")] });
    await openOffseason(off({ stage: "cutdown" }));
    expect(await screen.findByTestId("sim-offseason-bar")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Finish cut-down" })).toBeDisabled();
    // The same single action stays on the Team tab.
    mocked.getSimLineup.mockResolvedValue({ ok: true, reason: "", week: 0, slots: [], bench: [], projected_total: 0, warnings: [] } as never);
    fireEvent.click(screen.getByRole("tab", { name: /^Team/ }));
    expect(await screen.findByRole("button", { name: "Finish cut-down" })).toBeDisabled();
    expect(screen.getAllByTestId("sim-offseason-bar")).toHaveLength(1);
    expect(screen.getByText(/Cut 2 players to get to the roster limit first/)).toBeInTheDocument();
  });
});

describe("dynasty result", () => {
  it("shows titles, average finish and the per-year list, with a null grade and review", async () => {
    const done = game({ status: "complete", phase: "complete", dynasty: { season_no: 5, seasons: 5, year: 2030, stage: null, picks_held: 3, titles: 2, last_season: true } });
    mocked.listSimGames.mockResolvedValue({ ok: true, reason: "", games: [lite(done)] });
    mocked.getSimGame.mockResolvedValue({ ok: true, reason: "", game: done });
    mocked.getSimGameResult.mockResolvedValue({
      ok: true, reason: "",
      result: {
        mode: "dynasty", grade: null, review: null, decisions_that_mattered: [], champion: { team_id: "3", name: "My Team" }, final_standings: [], weeks: [],
        dynasty: {
          mode: "dynasty", seasons_total: 5, seasons_played: 2, start_year: 2026, complete: true, titles: 2, playoff_trips: 2, avg_finish: 1.5, wins: 22, losses: 6,
          best_season: { year: 2026, rank: 1, record: "12-2" }, picks_held: 3,
          by_year: [
            { season_no: 1, year: 2026, rank: 1, record: "12-2", pf: 1800, playoff_result: "champion", champion: { team_id: "3", name: "My Team", is_you: true }, avg_age: 26, top_scorers: [{ id: "1", name: "Quinn Back", pos: "QB", pts: 330 }] },
            { season_no: 2, year: 2027, rank: 2, record: "10-4", pf: 1700, playoff_result: "runner_up", champion: { team_id: "7", name: "Rivals", is_you: false }, avg_age: 26, top_scorers: [] },
          ],
        },
      },
    });
    render(<SimGameContent />);
    await openGame();
    const card = await screen.findByTestId("dynasty-result");
    expect(card).toHaveTextContent("2 titles");
    expect(card).toHaveTextContent("1.5");
    expect(card).toHaveTextContent("2026: 1st at 12-2");
    expect(screen.getAllByTestId("dynasty-year")).toHaveLength(2);
    expect(screen.getAllByTestId("dynasty-year")[0]).toHaveTextContent("Quinn Back 330.0");
  });
});

describe("picks in trades", () => {
  const pk = (id: string, season: number, round: number, orig: string, holder: string, hint: "early" | "mid" | "late" | null = null) => ({
    id, kind: "pick" as const, name: `${season} Round ${round}`, pos: "PICK" as const, team: "", season, round, orig_team_id: orig, orig_team_name: `Team ${orig}`, slot_hint: hint,
    age: null, adp: null, value: 40 + round, projection: 0, floor: 0, ceiling: 0, status: "healthy" as const, out_weeks: 0, bye_week: null, owner: { type: holder === "3" ? "you" as const : "ai" as const, team_id: holder, name: "x" },
  });

  async function openTrades() {
    const g = game();
    mocked.listSimGames.mockResolvedValue({ ok: true, reason: "", games: [lite(g)] });
    mocked.getSimGame.mockResolvedValue({ ok: true, reason: "", game: g });
    mocked.getSimHome.mockResolvedValue({ ok: true, reason: "", week: 4, phase: "regular_season", matchup: null, checklist: [], inbox: { count: 0, open: true, items: [] }, waiver_suggestions: [], bye_alerts: [], injuries: [], hot_cold: { hot: [], cold: [], wire: [] }, standings: { rows: [], playoff_spots: 6, games_left: 10, your_rank: 1, margin: 0, in_playoffs: true }, league: { recent: [], spotlight: null } });
    mocked.getSimPicks.mockResolvedValue({
      ok: true, reason: "", enabled: true, draft_year: 2027, rounds: 4, years: 3, you: [pk("pick:2027:1:3", 2027, 1, "3", "3", "early")],
      teams: [
        { team_id: "3", name: "My Team", is_you: true, picks: [pk("pick:2027:1:3", 2027, 1, "3", "3", "early")], total_value: 41 },
        { team_id: "7", name: "Rivals", is_you: false, picks: [pk("pick:2028:2:7", 2028, 2, "7", "7"), pk("pick:2027:2:9", 2027, 2, "9", "7", "late")], total_value: 82 },
      ],
    });
    mocked.getSimLineup.mockResolvedValue({ ok: true, reason: "", slots: [], bench: [] });
    mocked.getSimLeague.mockResolvedValue({ ok: true, reason: "", teams: [{ team_id: "7", name: "Rivals", is_you: false, power_rank: 2, persona: { id: "passive", label: "Passive", blurb: "Rarely deals." } }], standings: [] });
    mocked.getSimLeagueRosters.mockResolvedValue({ ok: true, reason: "", teams: [{ team_id: "7", name: "Rivals", is_you: false, power_rank: 2, persona: { id: "passive", label: "Passive", blurb: "Rarely deals." }, record: null, avg_age: 25, roster_size: 1, positions: [], strengths: [], needs: [], surplus: [], top_assets: [], players: [] }] });
    mocked.getSimGameTeam.mockImplementation(async (_g: string, t: string) => ({ ok: true, reason: "", team_id: t, players: [player(t === "3" ? "1" : "5", "QB", t === "3" ? "Quinn Back" : "Otis Opp")] }));
    mocked.getSimInbox.mockResolvedValue({
      ok: true, reason: "",
      items: [{ id: "o1", type: "trade_offer", from: { team_id: "7", name: "Rivals" }, you_give: [player("1", "QB", "Quinn Back")], you_get: [pk("pick:2028:2:7", 2028, 2, "7", "7")], message: "", expires_week: 5 }],
    });
    render(<SimGameContent />);
    await openGame();
    fireEvent.click(await screen.findByRole("tab", { name: "Trades" }));
  }

  it("an inbox offer renders a pick as a pick row, not a player", async () => {
    await openTrades();
    const row = await screen.findByTestId("pick-row");
    expect(row).toHaveTextContent("2028 Round 2");
    expect(row).not.toHaveTextContent(/trade value/i);
  });

  it("the builder's sheet has a Picks group on each side, grouped by year, and toggles pick ids", async () => {
    await openTrades();
    fireEvent.click(await screen.findByRole("tab", { name: "Make an offer" }));
    fireEvent.click(await screen.findByRole("button", { name: /Rivals.*Trade with this team/ }));
    // Your side: the sheet has a Picks tab beside the position-filtered players.
    fireEvent.click(await screen.findByRole("button", { name: /^You send/ }));
    let sheet = screen.getByRole("dialog");
    fireEvent.click(within(sheet).getByRole("tab", { name: /^Picks/ }));
    expect(sheet).toHaveTextContent("2027 picks");
    expect(within(sheet).getByRole("button", { name: "Add 2027 Round 1 (early)" })).toBeInTheDocument();
    expect(sheet).not.toHaveTextContent(/trade value/i);
    mocked.previewSimTrade.mockResolvedValue({ ok: true, reason: "", verdict: { decision: "accept", reason: "Fair.", chips: [] } });
    fireEvent.click(within(sheet).getByRole("button", { name: "Add 2027 Round 1 (early)" }));
    fireEvent.click(within(sheet).getByRole("button", { name: /^Add 1 to trade/ }));
    // Their side: picks grouped by year, earliest year first.
    fireEvent.click(screen.getByRole("button", { name: /^You receive/ }));
    sheet = screen.getByRole("dialog");
    fireEvent.click(within(sheet).getByRole("tab", { name: /^Picks/ }));
    const text = within(sheet).getByRole("list", { name: "Picks" }).textContent ?? "";
    expect(text.indexOf("2027 Round 2 (late)")).toBeLessThan(text.indexOf("2028 Round 2"));
    fireEvent.click(within(sheet).getByRole("button", { name: "Add 2028 Round 2" }));
    fireEvent.click(within(sheet).getByRole("button", { name: /^Add 1 to trade/ }));
    await waitFor(() => expect(mocked.previewSimTrade).toHaveBeenCalledWith("g1", { partner: "7", give: ["pick:2027:1:3"], get: ["pick:2028:2:7"] }));
    // Picks show in the offer summary as chips, and removing one clears it.
    expect(screen.getByRole("button", { name: "Remove 2027 Round 1 (early)" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Remove 2028 Round 2" })).toBeInTheDocument();
  });

});
