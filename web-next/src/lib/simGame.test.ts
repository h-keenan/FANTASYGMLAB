import { describe, expect, it } from "vitest";

import {
  SIM_QUEUE_MAX,
  SIM_TRADE_EMPTY,
  simAdvanceBlockers,
  simAdvanceLabel,
  simAdvanceWarnings,
  simAssignSlot,
  simClaimPayload,
  simDefaultFilter,
  simDraftClockLine,
  simFilterQuery,
  simFilterReducer,
  simGameAdvanceHitsPaywall,
  simGameErrorGate,
  simGameGate,
  simGameLiteLine,
  simGamePaywalled,
  simGamePreviewLine,
  simHeadshotId,
  simPlayerInitials,
  simPlayerSubline,
  simSlotRepeatsPosition,
  simGameReasonMessage,
  simGameStage,
  simLineupPayload,
  simNeedsDrop,
  simNewGameBlock,
  simPickLabel,
  simPlayoffRoundLabel,
  simQueueReducer,
  simRosterNeeds,
  simSlotAccepts,
  simSlotCandidates,
  simSlotLabels,
  simDeriveLayout,
  simImportableLeagues,
  simPositionsFor,
  simSettingsSummary,
  simSetupAdvancedChanged,
  simSetupBlock,
  simSetupBody,
  simSetupDefaults,
  simSetupSummary,
  simTradable,
  simTradeClosedReason,
  simTradeKey,
  simTradePayload,
  simTradeReady,
  simTradeReducer,
  simValueOverAdpLabel,
  simWeekHeading,
  type SimGame,
  type SimGamePlayer,
  type SimLineupSlot,
} from "./simGame";

function player(id: string, pos: SimGamePlayer["pos"], projection = 10): SimGamePlayer {
  return { id, name: `P${id}`, pos, team: "KC", age: 25, adp: 10, value: 50, projection, floor: 5, ceiling: 20, status: "healthy", out_weeks: 0, bye_week: 9 };
}

function game(overrides: Partial<SimGame> = {}): SimGame {
  return {
    id: "g1",
    status: "in_season",
    week: 4,
    phase: "regular_season",
    round: null,
    seed: 1,
    engine_version: "game-1.0.0",
    settings: { teams: 12, scoring: "ppr", difficulty: "normal", regular_weeks: 14, playoff_teams: 6, playoff_weeks: 3, trade_deadline_week: 10, roster_limit: 16, rounds: 14, slots: ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "K"], user_slot: 3, auto_lineup: false },
    you: null,
    this_week: null,
    pending: { claims: 0, inbox: 0, lineup_warnings: 0, roster_size: 16, roster_limit: 16, cuts_needed: 0 },
    can_trade: true,
    trade_deadline_week: 10,
    grade_letter: null,
    created_at: "",
    updated_at: "",
    ...overrides,
  };
}

describe("gating", () => {
  it("treats premium_required as a paywall, not an error", () => {
    const gate = simGameGate({ ok: true, reason: "premium_required", is_premium: false, upsell: { title: "t", body: "b" }, preview: { weeks_left: 0, paywall_week: 4, paywalled: true } });
    expect(gate).toEqual({ kind: "premium", upsell: { title: "t", body: "b" }, preview: { weeks_left: 0, paywall_week: 4, paywalled: true } });
  });

  it("a Pro caller at the game limit is blocked, a Free one gets the upsell", () => {
    expect(simGameGate({ reason: "game_limit_reached", is_premium: true, max_games: 3 }).kind).toBe("blocked");
    expect(simGameGate({ reason: "game_limit_reached", is_premium: false, upsell: null }).kind).toBe("premium");
  });

  it("maps storage, busy, conflict and rule reasons", () => {
    expect(simGameGate({ reason: "sim_storage_unavailable" })).toEqual({ kind: "unavailable", cause: "storage" });
    expect(simGameGate({ reason: "conflict" })).toEqual({ kind: "conflict" });
    expect(simGameGate({ reason: "player_taken" })).toMatchObject({ kind: "blocked", reason: "player_taken" });
    expect(simGameGate({ ok: true, reason: "" })).toEqual({ kind: "ready" });
    expect(simGameGate(null)).toEqual({ kind: "unavailable", cause: "off" });
  });

  it("prefers the engine's own message for a rule reason", () => {
    const gate = simGameGate({ reason: "wrong_phase", message: "The draft is over." });
    expect(gate).toMatchObject({ kind: "blocked", message: "The draft is over." });
  });

  it("classifies thrown errors by status", () => {
    expect(simGameErrorGate({ status: 404 })).toEqual({ kind: "unavailable", cause: "off" });
    expect(simGameErrorGate({ status: 409 })).toEqual({ kind: "conflict" });
    expect(simGameErrorGate({ status: 503, code: "server_busy" })).toEqual({ kind: "unavailable", cause: "busy" });
    expect(simGameErrorGate({ status: 500 })).toBeNull();
    expect(simGameErrorGate("boom")).toBeNull();
  });

  it("explains cuts needed with the count", () => {
    expect(simGameReasonMessage("roster_over_limit", { cuts_needed: 2 })).toContain("Cut 2 players");
    expect(simGameReasonMessage("roster_over_limit", { cuts_needed: 1 })).toContain("Cut 1 player ");
    expect(simGameReasonMessage("")).toBe("");
  });

  it("preview copy counts down and flips to paused", () => {
    expect(simGamePreviewLine(null)).toBeNull();
    expect(simGamePreviewLine({ weeks_left: 3, paywall_week: 4, paywalled: false })).toContain("3 weeks left");
    expect(simGamePreviewLine({ weeks_left: 1, paywall_week: 4, paywalled: false })).toContain("1 week left");
    expect(simGamePreviewLine({ weeks_left: 0, paywall_week: 4, paywalled: true })).toContain("paused at week 4");
    expect(simGamePaywalled({ weeks_left: 0, paywall_week: 4, paywalled: true })).toBe(true);
    expect(simGamePaywalled(null)).toBe(false);
  });

  it("warns before the advance that reaches the paywall week", () => {
    const preview = { weeks_left: 1, paywall_week: 4, paywalled: false };
    expect(simGameAdvanceHitsPaywall(preview, { week: 3 })).toBe(true);
    expect(simGameAdvanceHitsPaywall(preview, { week: 1 })).toBe(false);
    expect(simGameAdvanceHitsPaywall(null, { week: 9 })).toBe(false);
  });
});

describe("advance", () => {
  it("blocks on cuts and paywall, warns on lineup and inbox", () => {
    const g = game({ pending: { claims: 0, inbox: 2, lineup_warnings: 1, roster_size: 18, roster_limit: 16, cuts_needed: 2 } });
    expect(simAdvanceBlockers(g).map((b) => b.code)).toEqual(["cuts"]);
    expect(simAdvanceBlockers(g, { weeks_left: 0, paywall_week: 4, paywalled: true }).map((b) => b.code)).toEqual(["paywalled", "cuts"]);
    expect(simAdvanceBlockers(game()).length).toBe(0);
    expect(simAdvanceBlockers(null)[0].code).toBe("no_game");
    expect(simAdvanceWarnings(g)).toHaveLength(2);
    expect(simAdvanceWarnings(game())).toEqual([]);
  });

  it("labels the button for the phase", () => {
    expect(simAdvanceLabel(game())).toBe("Advance to week 5");
    expect(simAdvanceLabel(game({ phase: "playoffs", week: 16 }))).toBe("Play playoff week 16");
  });
});

describe("stage, headings and rounds", () => {
  it("maps status to stage", () => {
    expect(simGameStage({ status: "drafting" })).toBe("draft");
    expect(simGameStage({ status: "in_season" })).toBe("week");
    expect(simGameStage({ status: "playoffs" })).toBe("playoffs");
    expect(simGameStage({ status: "complete" })).toBe("final");
  });

  it("names playoff rounds from the week", () => {
    const s = { regular_weeks: 14, playoff_weeks: 3 };
    expect(simPlayoffRoundLabel(15, s)).toBe("Quarterfinals");
    expect(simPlayoffRoundLabel(16, s)).toBe("Semifinals");
    expect(simPlayoffRoundLabel(17, s)).toBe("Championship");
    expect(simWeekHeading(game())).toBe("Week 4 of 14");
    expect(simWeekHeading(game({ phase: "playoffs", week: 17 }))).toBe("Championship · Week 17");
  });

  it("describes saved games", () => {
    const base = { settings: { regular_weeks: 14 } };
    expect(simGameLiteLine({ ...base, status: "drafting", current_week: 0, grade_letter: null })).toBe("Draft in progress");
    expect(simGameLiteLine({ ...base, status: "in_season", current_week: 5, grade_letter: null })).toBe("Week 5 of 14");
    expect(simGameLiteLine({ ...base, status: "complete", current_week: 17, grade_letter: "B+" })).toBe("Finished · Grade B+");
  });

  it("explains why a new game is blocked", () => {
    expect(simNewGameBlock(0, 1, false)).toBeNull();
    expect(simNewGameBlock(1, 1, false)).toContain("Free includes 1 saved game");
    expect(simNewGameBlock(3, 3, true)).toContain("Delete one");
  });
});

describe("draft queue reducer", () => {
  it("adds uniquely, caps, removes and reorders", () => {
    let s = simQueueReducer({ ids: [] }, { type: "add", id: "a" });
    s = simQueueReducer(s, { type: "add", id: "b" });
    s = simQueueReducer(s, { type: "add", id: "a" });
    expect(s.ids).toEqual(["a", "b"]);
    s = simQueueReducer(s, { type: "move", id: "b", delta: -1 });
    expect(s.ids).toEqual(["b", "a"]);
    expect(simQueueReducer(s, { type: "move", id: "b", delta: -1 })).toBe(s);
    s = simQueueReducer(s, { type: "remove", id: "b" });
    expect(s.ids).toEqual(["a"]);
    const full = { ids: Array.from({ length: SIM_QUEUE_MAX }, (_, i) => `p${i}`) };
    expect(simQueueReducer(full, { type: "add", id: "x" })).toBe(full);
    expect(simQueueReducer({ ids: ["a", "a", "b"] }, { type: "set", ids: ["a", "a", "b"] }).ids).toEqual(["a", "b"]);
  });

  it("prunes drafted players", () => {
    const s = { ids: ["a", "b", "c"] };
    expect(simQueueReducer(s, { type: "prune", taken: ["b"] }).ids).toEqual(["a", "c"]);
    expect(simQueueReducer(s, { type: "prune", taken: ["z"] })).toBe(s);
  });
});

describe("player filter reducer", () => {
  it("resets to page 1 on any filter change but not on paging", () => {
    let f = simDefaultFilter();
    f = simFilterReducer(f, { type: "page", value: 3 });
    expect(f.page).toBe(3);
    f = simFilterReducer(f, { type: "pos", value: "RB" });
    expect(f).toMatchObject({ pos: "RB", page: 1 });
    f = simFilterReducer(f, { type: "page", value: 2 });
    f = simFilterReducer(f, { type: "sort", value: "value" });
    expect(f.page).toBe(1);
    expect(simFilterReducer(f, { type: "sort", value: "value" })).toBe(f);
    expect(simFilterReducer(f, { type: "page", value: -4 }).page).toBe(1);
  });

  it("builds a compact query string", () => {
    expect(simFilterQuery(simDefaultFilter())).toBe("page=1&page_size=40");
    const q = simFilterQuery(simDefaultFilter({ q: " Kelce ", pos: "TE", status: "available", sort: "adp", page: 2 }), 25);
    expect(q).toBe("q=Kelce&pos=TE&status=available&sort=adp&page=2&page_size=25");
  });
});

describe("draft helpers", () => {
  it("labels picks and the clock", () => {
    expect(simPickLabel(1, 12)).toBe("Round 1, pick 1");
    expect(simPickLabel(14, 12)).toBe("Round 2, pick 2");
    const base = { status: "in_progress" as const, pick_no: 5, total_picks: 168, picks_until_you: 3, on_the_clock: { team_id: "2", name: "Rivals", is_you: false } };
    expect(simDraftClockLine(base)).toBe("Rivals is picking. Your pick is 3 picks away.");
    expect(simDraftClockLine({ ...base, on_the_clock: { team_id: "3", name: "Me", is_you: true } })).toBe("You are on the clock.");
    expect(simDraftClockLine({ ...base, status: "complete" })).toBe("Draft complete.");
  });

  it("counts roster needs against starter slots", () => {
    const needs = simRosterNeeds([player("1", "RB"), player("2", "RB"), player("3", "RB"), player("4", "QB")], ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "K"]);
    expect(needs.find((n) => n.pos === "RB")).toEqual({ pos: "RB", have: 3, starters: 2 });
    expect(needs.find((n) => n.pos === "QB")).toEqual({ pos: "QB", have: 1, starters: 1 });
    expect(needs.find((n) => n.pos === "K")).toEqual({ pos: "K", have: 0, starters: 1 });
  });

  it("labels picks against ADP", () => {
    expect(simValueOverAdpLabel(4.2)).toBe("Steal +4");
    expect(simValueOverAdpLabel(-6)).toBe("Reach -6");
    expect(simValueOverAdpLabel(0.2)).toBe("On ADP");
    expect(simValueOverAdpLabel(null)).toBe("");
  });
});

describe("lineup", () => {
  const slots = (...entries: [SimLineupSlot["slot"], SimGamePlayer | null][]): SimLineupSlot[] => entries.map(([slot, p]) => ({ slot, player: p }));

  it("knows slot eligibility", () => {
    expect(simSlotAccepts("FLEX", "RB")).toBe(true);
    expect(simSlotAccepts("FLEX", "QB")).toBe(false);
    expect(simSlotAccepts("FLEX", "K")).toBe(false);
    expect(simSlotAccepts("RB", "WR")).toBe(false);
    expect(simSlotAccepts("K", "K")).toBe(true);
  });

  it("numbers duplicate slots only", () => {
    expect(simSlotLabels(slots(["QB", null], ["RB", null], ["RB", null], ["FLEX", null]))).toEqual(["QB", "RB1", "RB2", "FLEX"]);
  });

  it("lists eligible candidates best projection first", () => {
    const a = player("a", "RB", 8);
    const b = player("b", "WR", 20);
    const c = player("c", "RB", 15);
    const cands = simSlotCandidates("FLEX", slots(["RB", c]), [a, b]);
    expect(cands.map((x) => x.player.id)).toEqual(["b", "c", "a"]);
    expect(cands.find((x) => x.player.id === "c")?.from).toBe("slot");
  });

  it("swaps a bench player in and benches the displaced starter", () => {
    const starter = player("s", "RB");
    const bench = player("b", "RB");
    const out = simAssignSlot({ slots: slots(["RB", starter]), bench: [bench] }, 0, bench);
    expect(out.slots[0].player?.id).toBe("b");
    expect(out.bench.map((p) => p.id)).toEqual(["s"]);
  });

  it("swaps two starters when both fit, else empties the vacated slot", () => {
    const rb = player("rb", "RB");
    const rb3 = player("rb3", "RB");
    const swapped = simAssignSlot({ slots: slots(["FLEX", rb], ["RB", rb3]), bench: [] }, 0, rb3);
    expect(swapped.slots.map((s) => s.player?.id)).toEqual(["rb3", "rb"]);
    expect(swapped.bench).toEqual([]);
    // The displaced RB cannot play WR: the WR slot empties and he goes to the bench.
    const wr = player("wr", "WR");
    const emptied = simAssignSlot({ slots: slots(["FLEX", rb], ["WR", wr]), bench: [] }, 0, wr);
    expect(emptied.slots.map((s) => s.player?.id ?? null)).toEqual(["wr", null]);
    expect(emptied.bench.map((p) => p.id)).toEqual(["rb"]);
  });

  it("refuses an ineligible assignment and can empty a slot", () => {
    const edit = { slots: slots(["QB", player("q", "QB")]), bench: [player("r", "RB")] };
    expect(simAssignSlot(edit, 0, player("r", "RB"))).toBe(edit);
    const emptied = simAssignSlot(edit, 0, null);
    expect(emptied.slots[0].player).toBeNull();
    expect(emptied.bench.map((p) => p.id).sort()).toEqual(["q", "r"]);
  });

  it("builds the exact PUT payload in slot order", () => {
    expect(simLineupPayload(slots(["QB", player("q", "QB")], ["K", null]))).toEqual({ slots: [{ slot: "QB", player_id: "q" }, { slot: "K", player_id: null }] });
  });
});

describe("waivers", () => {
  it("needs a drop only when the roster is full", () => {
    expect(simNeedsDrop(16, 16)).toBe(true);
    expect(simNeedsDrop(15, 16)).toBe(false);
    expect(simNeedsDrop(15, 16, 1)).toBe(true);
  });
  it("builds the claim payload", () => {
    expect(simClaimPayload({ add: null, drop: null, startSlot: null })).toBeNull();
    expect(simClaimPayload({ add: player("a", "WR"), drop: player("d", "WR"), startSlot: "WR" })).toEqual({ add: "a", drop: "d", start_slot: "WR" });
    expect(simClaimPayload({ add: player("a", "WR"), drop: null, startSlot: null })).toEqual({ add: "a", drop: null, start_slot: null });
  });
});

describe("trade builder", () => {
  it("caps each side at three and toggles off", () => {
    let s = SIM_TRADE_EMPTY;
    s = simTradeReducer(s, { type: "partner", teamId: "7" });
    for (const id of ["a", "b", "c", "d"]) s = simTradeReducer(s, { type: "toggle", side: "give", id });
    expect(s.give).toEqual(["a", "b", "c"]);
    s = simTradeReducer(s, { type: "toggle", side: "give", id: "b" });
    expect(s.give).toEqual(["a", "c"]);
  });

  it("changing partner clears what you asked for but keeps what you give", () => {
    let s = simTradeReducer(SIM_TRADE_EMPTY, { type: "partner", teamId: "7" });
    s = simTradeReducer(s, { type: "toggle", side: "give", id: "a" });
    s = simTradeReducer(s, { type: "toggle", side: "get", id: "x" });
    const next = simTradeReducer(s, { type: "partner", teamId: "8" });
    expect(next).toEqual({ partner: "8", give: ["a"], get: [] });
    expect(simTradeReducer(s, { type: "partner", teamId: "7" })).toBe(s);
  });

  it("is ready only with a partner and both sides, and keys order-independently", () => {
    expect(simTradeReady({ partner: "7", give: ["a"], get: [] })).toBe(false);
    expect(simTradeReady({ partner: null, give: ["a"], get: ["b"] })).toBe(false);
    expect(simTradeReady({ partner: "7", give: ["a"], get: ["b"] })).toBe(true);
    expect(simTradeKey({ partner: "7", give: ["b", "a"], get: ["c"] })).toBe(simTradeKey({ partner: "7", give: ["a", "b"], get: ["c"] }));
    expect(simTradePayload({ partner: "7", give: ["a"], get: [] })).toBeNull();
    expect(simTradePayload({ partner: "7", give: ["a"], get: ["b"] })).toEqual({ partner: "7", give: ["a"], get: ["b"] });
  });

  it("explains why trading is closed", () => {
    expect(simTradeClosedReason({ can_trade: true, phase: "regular_season", trade_deadline_week: 10 })).toBeNull();
    expect(simTradeClosedReason({ can_trade: false, phase: "playoffs", trade_deadline_week: 10 })).toMatch(/playoffs/);
    expect(simTradeClosedReason({ can_trade: false, phase: "regular_season", trade_deadline_week: 10 })).toMatch(/deadline/);
  });
});


describe("league settings and start modes (setup)", () => {
  const options = {
    options: {
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
    },
    layout: { base_slots: ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX"], draft_spare_spots: 2 },
  } as unknown as Parameters<typeof simSetupDefaults>[0];

  it("quick start is 12 teams, half PPR and the standard lineup", () => {
    const d = simSetupDefaults(options);
    expect(d).toMatchObject({ start: "fresh", teams: 12, scoring: "half", tePremium: 0, superflex: false, includeK: true, includeDef: false, bench: 8 });
    expect(simSetupDefaults(null)).toMatchObject({ teams: 12, scoring: "half", bench: 8, includeK: true });
    expect(simSetupBody(d)).toEqual({ difficulty: "normal", auto_lineup: false, tiebreaker: "points_for", teams: 12, scoring: "half", te_premium: 0, superflex: false, include_k: true, include_def: false, bench: 8, mode: "redraft", user_slot: null });
  });

  it("derives lineup, roster size and draft rounds exactly like the engine (same table as the backend test)", () => {
    const table: [boolean, boolean, boolean, number, number, number, number][] = [
      [false, true, false, 8, 8, 16, 14],
      [true, true, false, 8, 9, 17, 15],
      [true, false, true, 6, 9, 15, 13],
      [false, false, false, 4, 7, 11, 9],
      [true, true, true, 10, 10, 20, 18],
    ];
    for (const [superflex, includeK, includeDef, bench, slots, limit, rounds] of table) {
      const got = simDeriveLayout({ superflex, includeK, includeDef, bench });
      expect([got.slots.length, got.rosterLimit, got.rounds]).toEqual([slots, limit, rounds]);
      expect([got.slots.includes("SUPER_FLEX"), got.slots.includes("K"), got.slots.includes("DEF")]).toEqual([superflex, includeK, includeDef]);
    }
    expect(simDeriveLayout(simSetupDefaults(null)).slots).toEqual(["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "K"]);
  });

  it("sends advanced options and counts what changed", () => {
    const d = simSetupDefaults(options);
    const s = { ...d, teams: 14, scoring: "std" as const, tePremium: 0.5, superflex: true, includeDef: true, bench: 6, slot: "3", name: " Mine " };
    expect(simSetupBody(s)).toMatchObject({ teams: 14, scoring: "std", te_premium: 0.5, superflex: true, include_def: true, bench: 6, user_slot: 3, team_name: "Mine" });
    expect(simSetupAdvancedChanged(s, d)).toBe(6);
    expect(simSetupAdvancedChanged(d, d)).toBe(0);
    expect(simSetupSummary(s, options?.layout)).toBe("14 teams, 14-round snake draft. Starters: QB, RB, RB, WR, WR, TE, FLEX, SUPER_FLEX, K, DEF. Roster 16.");
  });

  it("starting from a league sends only what the league does not decide, and needs a league", () => {
    const d = { ...simSetupDefaults(options), start: "league" as const, teams: 8, name: "", leagueId: "" };
    expect(simSetupBlock(d)).toMatch(/Pick one of your leagues/);
    const ready = { ...d, leagueId: "123", difficulty: "hard" as const, auto: true };
    expect(simSetupBlock(ready)).toBeNull();
    expect(simSetupBody(ready)).toEqual({ difficulty: "hard", auto_lineup: true, tiebreaker: "points_for", start: "league", league_id: "123" });
    expect(simSetupSummary(ready)).toMatch(/nothing changes in your real league/);
    expect(simSetupBlock(simSetupDefaults(options))).toBeNull();
  });

  it("only offers Sleeper leagues (imported platforms carry a prefix)", () => {
    const rows = [{ league_id: "111", league_name: "A" }, { league_id: "espn:5:2026", league_name: "B" }, { league_id: "mfl:1:2026", league_name: "C" }, { league_id: "", league_name: "D" }];
    expect(simImportableLeagues(rows).map((r) => r.league_id)).toEqual(["111"]);
    expect(simImportableLeagues(null)).toEqual([]);
  });

  it("knows superflex, rec flex, kickers and defenses", () => {
    expect(simSlotAccepts("SUPER_FLEX", "QB")).toBe(true);
    expect(simSlotAccepts("SUPER_FLEX", "K")).toBe(false);
    expect(simSlotAccepts("FLEX", "QB")).toBe(false);
    expect(simSlotAccepts("REC_FLEX", "WR")).toBe(true);
    expect(simSlotAccepts("REC_FLEX", "RB")).toBe(false);
    expect(simSlotAccepts("DEF", "DEF")).toBe(true);
    expect(simSlotAccepts("K", "DEF")).toBe(false);
    expect(simTradable("K")).toBe(false);
    expect(simTradable("DEF")).toBe(false);
    expect(simTradable("QB")).toBe(true);
  });

  it("filters positions and roster needs to what the league plays", () => {
    const std = ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "K"] as const;
    expect(simPositionsFor([...std])).toEqual(["QB", "RB", "WR", "TE", "K"]);
    expect(simPositionsFor([...std, "DEF"])).toEqual(["QB", "RB", "WR", "TE", "K", "DEF"]);
    expect(simPositionsFor(["QB", "RB", "WR", "TE", "FLEX", "SUPER_FLEX"])).toEqual(["QB", "RB", "WR", "TE"]);
    const needs = simRosterNeeds([player("1", "QB")], ["QB", "RB", "FLEX", "SUPER_FLEX", "DEF"]);
    expect(needs.map((n) => n.pos)).toEqual(["QB", "RB", "WR", "TE", "DEF"]);
    expect(needs.find((n) => n.pos === "QB")).toEqual({ pos: "QB", have: 1, starters: 1 });
    expect(needs.find((n) => n.pos === "DEF")).toEqual({ pos: "DEF", have: 0, starters: 1 });
  });

  it("summarizes saved league settings and tolerates older saves", () => {
    expect(simSettingsSummary({ teams: 14, scoring: "half", te_premium: 0.5, superflex: true, include_def: true, include_k: false, start: "league" })).toBe("14 teams · Half PPR · TE premium +0.5 · Superflex · DEF · No kickers · From your league");
    expect(simSettingsSummary({ teams: 12, scoring: "ppr" })).toBe("12 teams · PPR");
    expect(simSettingsSummary(undefined)).toBe("");
    expect(simGameReasonMessage("team_not_found")).toMatch(/Sleeper username/);
    expect(simGameReasonMessage("def_unavailable")).toMatch(/Advanced options/);
  });
});

describe("player photo helpers", () => {
  it("uses the payload headshot id, else a numeric Sleeper id, else nothing", () => {
    expect(simHeadshotId({ id: "4046", headshot_id: "4046" })).toBe("4046");
    expect(simHeadshotId({ id: "4046" })).toBe("4046");
    expect(simHeadshotId({ id: "p0001", headshot_id: null })).toBeNull();
    expect(simHeadshotId({ id: "DEF-NYG" })).toBeNull();
    expect(simHeadshotId({ id: "4046", headshot_id: null })).toBeNull();
  });
  it("builds fallback initials, using the team code for a defense", () => {
    expect(simPlayerInitials({ name: "Patrick Mahomes II", pos: "QB", team: "KC" })).toBe("PI");
    expect(simPlayerInitials({ name: "Cher", pos: "WR", team: null })).toBe("C");
    expect(simPlayerInitials({ name: "NYG D/ST", pos: "DEF", team: "NYG" })).toBe("NYG");
    expect(simPlayerInitials({ name: "", pos: "WR", team: null })).toBe("");
  });
  it("builds a subline from a partial brief", () => {
    expect(simPlayerSubline({ team: "KC" })).toBe("KC");
    expect(simPlayerSubline({})).toBe("");
  });
});

describe("lineup slot vs position chip", () => {
  it("repeats only when the slot is the player's own position", () => {
    expect(simSlotRepeatsPosition("RB", "RB")).toBe(true);
    expect(simSlotRepeatsPosition("FLEX", "RB")).toBe(false);
    expect(simSlotRepeatsPosition("SUPER_FLEX", "QB")).toBe(false);
  });
});
