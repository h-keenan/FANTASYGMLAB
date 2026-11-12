import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SimGameContent } from "./SimGameContent";
import { api } from "@/lib/api";
import type { SimGame, SimGameOptionsResponse, SimGamePlayer, SimLineupResponse } from "@/lib/simGame";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  const names = [
    "getSimGameOptions", "listSimGames", "createSimGame", "getSimGame", "deleteSimGame", "getSimDraft", "simDraftPick", "simDraftAuto",
    "putSimDraftQueue", "getSimGamePlayers", "getSimGamePlayer", "getSimGameTeam", "getSimLineup", "putSimLineup", "autoSimLineup",
    "claimSimWaiver", "cancelSimWaiver", "cutSimPlayer", "previewSimTrade", "sendSimTrade", "getSimInbox", "respondSimInbox",
    "advanceSimGame", "revertSimWeek", "getSimLeague", "getSimGameResult",
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
  ok: true, reason: "", week: 4, slots: [{ slot: "QB", player: player("1", "QB", "Quinn Back") }, { slot: "RB", player: null }], bench: [player("2", "RB", "Benny Bench")],
  projected_total: 121.4, warnings: [], roster_size: 16, roster_limit: 16, opponent: null, locked: false,
};

const premiumBody = { ok: true, reason: "premium_required", is_premium: false, upsell: { title: "Keep your season going", body: "Pro unlocks the rest of the season." }, preview: { weeks_left: 0, paywall_week: 4, paywalled: true } };

function openFirstGame() {
  return screen.findByRole("button", { name: /Open game/ }).then((b) => fireEvent.click(b));
}

describe("SimGameContent", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mocked.getSimGameOptions.mockResolvedValue(options());
    mocked.getSimGame.mockResolvedValue({ ok: true, reason: "", game: game() });
    mocked.getSimLineup.mockResolvedValue(lineup);
    mocked.getSimGamePlayers.mockResolvedValue({ ok: true, reason: "", items: [], total: 0, page: 1, page_size: 40 });
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

  it("Free past week 3: Advance becomes Go Pro, never calls the API, and reads still render", async () => {
    mocked.getSimGameOptions.mockResolvedValue(options({ is_premium: false, max_games: 1, preview: { weeks_left: 0, paywall_week: 4, paywalled: true } }));
    mocked.listSimGames.mockResolvedValue({ ok: true, reason: "", games: [lite(game())] });
    mocked.getSimGame.mockResolvedValue({ ok: true, reason: "", game: game(), preview: { weeks_left: 0, paywall_week: 4, paywalled: true } });
    render(<SimGameContent />);
    await openFirstGame();
    expect(await screen.findByRole("link", { name: "Go Pro to continue" })).toHaveAttribute("href", "/premium");
    expect(screen.queryByRole("button", { name: /Advance to week/ })).not.toBeInTheDocument();
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
    fireEvent.click(await screen.findByRole("button", { name: "Advance to week 4" }));
    expect(await screen.findByTestId("sim-paywall")).toHaveTextContent("Pro unlocks the rest of the season.");
    expect(mocked.advanceSimGame).toHaveBeenCalledWith("g1", 3);
    expect(screen.getByText("Quinn Back")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Keep looking around" }));
    expect(screen.queryByTestId("sim-paywall")).not.toBeInTheDocument();
  });

  it("an over-limit roster blocks Advance before any call", async () => {
    const over = game({ pending: { claims: 0, inbox: 0, lineup_warnings: 0, roster_size: 18, roster_limit: 16, cuts_needed: 2 } });
    mocked.listSimGames.mockResolvedValue({ ok: true, reason: "", games: [lite(over)] });
    mocked.getSimGame.mockResolvedValue({ ok: true, reason: "", game: over });
    render(<SimGameContent />);
    await openFirstGame();
    fireEvent.click(await screen.findByRole("button", { name: "Advance to week 5" }));
    expect(await screen.findAllByText(/Cut 2 players/)).not.toHaveLength(0);
    expect(mocked.advanceSimGame).not.toHaveBeenCalled();
  });

  it("Advance plays the week, shows the recap, then returns to the team", async () => {
    mocked.listSimGames.mockResolvedValue({ ok: true, reason: "", games: [lite(game())] });
    mocked.advanceSimGame.mockResolvedValue({
      ok: true, reason: "", is_premium: true, game: game({ week: 5 }),
      recap: { week: 4, kind: "regular", round: null, your_game: { opponent_id: "7", opponent_name: "Rivals", your_pts: 128.4, opp_pts: 109.7, result: "win", starters: [] }, scores: [], season_complete: false, champion: null, next_week: 5 },
    });
    render(<SimGameContent />);
    await openFirstGame();
    fireEvent.click(await screen.findByRole("button", { name: "Advance to week 5" }));
    expect(await screen.findByTestId("week-recap")).toHaveTextContent("Week 4 recap");
    expect(screen.getByText("Win")).toBeInTheDocument();
    expect(mocked.advanceSimGame).toHaveBeenCalledWith("g1", 4);
    fireEvent.click(screen.getByRole("button", { name: "Back to your team" }));
    await waitFor(() => expect(screen.queryByTestId("week-recap")).not.toBeInTheDocument());
    expect(screen.getByTestId("game-heading")).toHaveTextContent("Week 5 of 14");
  });

  it("a raced write (409) reloads the game and says so instead of failing", async () => {
    mocked.listSimGames.mockResolvedValue({ ok: true, reason: "", games: [lite(game())] });
    mocked.advanceSimGame.mockRejectedValue(Object.assign(new Error("Request failed with status 409."), { status: 409 }));
    render(<SimGameContent />);
    await openFirstGame();
    fireEvent.click(await screen.findByRole("button", { name: "Advance to week 5" }));
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
    fireEvent.click(await screen.findByRole("button", { name: "Draft Rory Runner" }));
    expect(await screen.findByTestId("draft-recap")).toHaveTextContent("Draft grade A-");
    expect(mocked.simDraftPick).toHaveBeenCalledWith("g1", "10");
    fireEvent.click(screen.getByRole("button", { name: "Start the season" }));
    expect(await screen.findByTestId("game-heading")).toHaveTextContent("Week 1 of 14");
  });
});
