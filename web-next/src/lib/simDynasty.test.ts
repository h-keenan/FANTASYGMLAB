import { describe, expect, it } from "vitest";

import {
  SIM_TRADE_EMPTY,
  simAdvanceLabel,
  simArchiveToYear,
  simCanMoveToIr,
  simCanMoveToRoster,
  simCanMoveToTaxi,
  simDynastyPaths,
  simDynastySummaryView,
  simGameGate,
  simGameStage,
  simIsDynastyResult,
  simIsPick,
  simMoverText,
  simOffseasonCta,
  simOffseasonSteps,
  simParsePickId,
  simPickGroups,
  simPickLabelText,
  simPickSlotHint,
  simPickViaLine,
  simPicksOf,
  simPicksSummaryLine,
  simPlayerChips,
  simReserveActions,
  simReservesOn,
  simRetireesSorted,
  simRookieClockLine,
  simSetupBody,
  simSetupCountOptions,
  simSetupDefaults,
  simSetupDynastyNote,
  simSetupModes,
  simSetupSummary,
  simSetupTaxiDefault,
  simSettingsSummary,
  simTradeMaxPerSide,
  simTradeReducer,
  simWeekHeading,
  normalizeSimResult,
  type SimGameOptionsResponse,
  type SimGamePlayer,
  type SimPickAsset,
  type SimReserves,
  type SimSeasonArchive,
} from "./simGame";
import { simDraftRowChips } from "./simDraft";

const reserves = (over: Partial<SimReserves> = {}): SimReserves => ({ enabled: true, ir_slots: 2, taxi_slots: 4, taxi_years: 2, ir_used: 0, taxi_used: 0, ...over });

const row = (over: Partial<SimGamePlayer> = {}): SimGamePlayer => ({
  id: "p1", name: "Rey Runner", pos: "RB", team: "KC", age: 22, adp: 40, projection: 9, floor: 3, ceiling: 18,
  status: "healthy", out_weeks: 0, bye_week: 9, squad: "roster", taxi_eligible: true, rookie: false, ...over,
});

const pick = (over: Partial<SimPickAsset> = {}): SimPickAsset => ({
  id: "pick:2027:1:3", kind: "pick", name: "2027 Round 1", pos: "PICK", team: "", season: 2027, round: 1, orig_team_id: "3", orig_team_name: "My Team",
  slot_hint: "early", age: null, adp: null, projection: 0, floor: 0, ceiling: 0, status: "healthy", out_weeks: 0, bye_week: null,
  owner: { type: "you", team_id: "3", name: "My Team" }, ...over,
});

const options = (): SimGameOptionsResponse => ({
  options: {
    mode: { values: ["redraft", "dynasty"], default: "redraft" },
    teams: { values: [8, 10, 12], default: 12 }, scoring: { values: ["ppr", "half", "std"], default: "half" },
    difficulty: { values: ["easy", "normal", "hard"], default: "normal" }, user_slot: { min: 1, max: 12, default: null }, auto_lineup: { default: false },
    seasons: { values: [3, 4, 5], default: 5 }, rookie_rounds: { values: [2, 3, 4, 5], default: 4 },
    ir_slots: { min: 0, max: 4, default: 2 }, taxi_slots: { min: 0, max: 8, default: 0, default_dynasty: 4 }, taxi_years: { values: [1, 2, 3, 4], default: 2 },
  },
});

describe("dynasty setup", () => {
  it("keeps the quick start body exactly as before (redraft, no reserve or dynasty fields)", () => {
    const d = simSetupDefaults(options());
    expect(d).toMatchObject({ mode: "redraft", seasons: 5, rookieRounds: 4, irSlots: null, taxiSlots: null, taxiYears: null });
    const body = simSetupBody(d);
    expect(body.mode).toBe("redraft");
    for (const key of ["seasons", "rookie_rounds", "ir_slots", "taxi_slots", "taxi_years"]) expect(body).not.toHaveProperty(key);
  });

  it("sends dynasty with seasons and rookie rounds, and reserve fields only when chosen", () => {
    const d = { ...simSetupDefaults(options()), mode: "dynasty" as const, seasons: 3, rookieRounds: 2, irSlots: 1, taxiSlots: 6, taxiYears: 3 };
    expect(simSetupBody(d)).toMatchObject({ mode: "dynasty", seasons: 3, rookie_rounds: 2, ir_slots: 1, taxi_slots: 6, taxi_years: 3 });
    const plain = simSetupBody({ ...simSetupDefaults(options()), mode: "dynasty" });
    expect(plain).toMatchObject({ mode: "dynasty", seasons: 5, rookie_rounds: 4 });
    expect(plain).not.toHaveProperty("ir_slots");
  });

  it("carries mode dynasty through a start from my league", () => {
    const d = { ...simSetupDefaults(options()), start: "league" as const, leagueId: "123", rosterId: "7", mode: "dynasty" as const };
    expect(simSetupBody(d)).toEqual({
      difficulty: "normal", auto_lineup: false, tiebreaker: "points_for", start: "league", league_id: "123", roster_id: "7",
      mode: "dynasty", seasons: 5, rookie_rounds: 4,
    });
    const redraft = simSetupBody({ ...d, mode: "redraft" });
    expect(redraft).not.toHaveProperty("mode");
    expect(simSetupDynastyNote(d)).toMatch(/picks, taxi squad and IR/);
    expect(simSetupDynastyNote({ start: "league", mode: "redraft" })).toBeNull();
    expect(simSetupSummary(d)).toMatch(/Dynasty: up to 5 seasons/);
  });

  it("offers the modes the options allow, and the taxi default per mode", () => {
    expect(simSetupModes(options()).map((m) => m.value)).toEqual(["redraft", "dynasty"]);
    expect(simSetupModes(null).map((m) => m.value)).toEqual(["redraft"]);
    expect(simSetupTaxiDefault(options(), "redraft")).toBe(0);
    expect(simSetupTaxiDefault(options(), "dynasty")).toBe(4);
    expect(simSetupCountOptions(2, 2)[0]).toEqual({ label: "Default (2)", value: "" });
    expect(simSetupCountOptions(2, null).map((o) => o.value)).toEqual(["", "0", "1", "2"]);
  });

  it("summarises a saved dynasty game", () => {
    expect(simSettingsSummary({ teams: 12, scoring: "half", mode: "dynasty", seasons: 5 })).toMatch(/^Dynasty \(5 seasons\)/);
  });
});

describe("picks", () => {
  it("labels, parses and hints", () => {
    expect(simPickLabelText(pick())).toBe("2027 Round 1 (early)");
    expect(simPickLabelText(pick({ slot_hint: null, season: 2028, round: 3 }))).toBe("2028 Round 3");
    expect(simPickLabelText({ id: "pick:2029:2:9" })).toBe("2029 Round 2");
    expect(simParsePickId("pick:2027:1:3")).toEqual({ season: 2027, round: 1, origTeamId: "3" });
    expect(simParsePickId("p1")).toBeNull();
    expect(simIsPick(pick())).toBe(true);
    expect(simIsPick(row())).toBe(false);
    expect(simPickSlotHint(pick({ slot_hint: "late" }))).toMatch(/bottom/);
    expect(simPickSlotHint(pick({ slot_hint: null, season: 2029 }), 2027)).toMatch(/after that season/);
  });

  it("says where a pick came from", () => {
    expect(simPickViaLine(pick({ own: true }))).toBeNull();
    expect(simPickViaLine(pick({ own: false, orig_team_name: "Rivals" }))).toBe("via Rivals");
    expect(simPickViaLine(pick({ orig_team_id: "7", orig_team_name: "Rivals" }))).toBe("via Rivals");
    expect(simPickViaLine(pick())).toBeNull();
  });

  it("groups by year then round and summarises", () => {
    const picks = [
      pick({ id: "pick:2028:2:3", season: 2028, round: 2 }),
      pick({ id: "pick:2027:2:3", season: 2027, round: 2 }),
      pick({ id: "pick:2027:1:3", season: 2027, round: 1 }),
    ];
    const groups = simPickGroups(picks);
    expect(groups.map((g) => g.season)).toEqual([2027, 2028]);
    expect(groups[0].rounds.map((r) => r.round)).toEqual([1, 2]);
    expect(simPicksSummaryLine(picks)).toBe("3 picks: 2027 (2), 2028 (1)");
    expect(simPicksSummaryLine([])).toBe("No picks");
    expect(simPickGroups(null)).toEqual([]);
  });

  it("finds a team's picks", () => {
    const res = { you: [pick()], teams: [{ team_id: "3", name: "Me", is_you: true, picks: [pick()], total_value: 61 }, { team_id: "7", name: "Them", is_you: false, picks: [], total_value: 0 }] };
    expect(simPicksOf(res, "3")).toHaveLength(1);
    expect(simPicksOf(res, "7")).toHaveLength(0);
    expect(simPicksOf(res, undefined)).toHaveLength(1);
    expect(simPicksOf(null, "3")).toEqual([]);
  });

  it("lets a dynasty trade side hold 4 assets, a redraft one 3, picks included", () => {
    expect(simTradeMaxPerSide({ mode: "dynasty" })).toBe(4);
    expect(simTradeMaxPerSide({ mode: "redraft" })).toBe(3);
    expect(simTradeMaxPerSide(undefined)).toBe(3);
    let s = SIM_TRADE_EMPTY;
    for (const id of ["a", "b", "pick:2027:1:3", "pick:2027:2:3", "e"]) s = simTradeReducer(s, { type: "toggle", side: "give", id, max: 4 });
    expect(s.give).toEqual(["a", "b", "pick:2027:1:3", "pick:2027:2:3"]);
    s = simTradeReducer(SIM_TRADE_EMPTY, { type: "toggle", side: "give", id: "a" });
    for (const id of ["b", "c", "d"]) s = simTradeReducer(s, { type: "toggle", side: "give", id });
    expect(s.give).toHaveLength(3);
  });
});

describe("IR and taxi legality", () => {
  it("IR needs an injured active player and an open slot", () => {
    const hurt = row({ status: "out", out_weeks: 3 });
    expect(simCanMoveToIr(hurt, { reserves: reserves() })).toEqual({ ok: true });
    expect(simCanMoveToIr(row(), { reserves: reserves() })).toEqual({ ok: false, reason: "ir_ineligible" });
    expect(simCanMoveToIr(hurt, { reserves: reserves({ ir_used: 2 }) })).toEqual({ ok: false, reason: "ir_full" });
    expect(simCanMoveToIr(hurt, { reserves: reserves({ ir_slots: 0 }) })).toEqual({ ok: false, reason: "ir_full" });
    expect(simCanMoveToIr({ ...hurt, squad: "taxi" }, { reserves: reserves() })).toEqual({ ok: false, reason: "ir_ineligible" });
    expect(simCanMoveToIr(hurt, { reserves: null })).toEqual({ ok: false, reason: "reserves_unavailable" });
  });

  it("taxi needs an eligible active player and an open slot", () => {
    expect(simCanMoveToTaxi(row(), { reserves: reserves() })).toEqual({ ok: true });
    expect(simCanMoveToTaxi(row({ taxi_eligible: false }), { reserves: reserves() })).toEqual({ ok: false, reason: "taxi_ineligible" });
    expect(simCanMoveToTaxi(row({ pos: "K" }), { reserves: reserves() })).toEqual({ ok: false, reason: "taxi_ineligible" });
    expect(simCanMoveToTaxi(row(), { reserves: reserves({ taxi_used: 4 }) })).toEqual({ ok: false, reason: "taxi_full" });
    expect(simCanMoveToTaxi(row({ squad: "ir" }), { reserves: reserves() })).toEqual({ ok: false, reason: "taxi_ineligible" });
  });

  it("activate and promote need an open roster spot", () => {
    const ctx = { reserves: reserves(), rosterSize: 16, rosterLimit: 16 };
    expect(simCanMoveToRoster(row({ squad: "ir" }), ctx)).toEqual({ ok: false, reason: "roster_full" });
    expect(simCanMoveToRoster(row({ squad: "taxi" }), { ...ctx, rosterSize: 15 })).toEqual({ ok: true });
    expect(simCanMoveToRoster(row(), ctx)).toEqual({ ok: false });
  });

  it("offers only the moves that fit where he sits", () => {
    const ctx = { reserves: reserves(), rosterSize: 10, rosterLimit: 16 };
    expect(simReserveActions(row({ squad: "ir" }), ctx).map((a) => a.label)).toEqual(["Activate"]);
    expect(simReserveActions(row({ squad: "taxi" }), ctx).map((a) => a.label)).toEqual(["Promote"]);
    expect(simReserveActions(row(), ctx).map((a) => [a.label, a.check.ok])).toEqual([["Move to IR", false], ["Move to taxi", true]]);
  });

  it("knows when the game has reserves and chips a row", () => {
    expect(simReservesOn({ reserve_v: 1, ir_slots: 2, taxi_slots: 0 })).toBe(true);
    expect(simReservesOn({ reserve_v: 1, ir_slots: 0, taxi_slots: 0 })).toBe(false);
    expect(simReservesOn({})).toBe(false);
    expect(simReservesOn({}, reserves())).toBe(true);
    expect(simReservesOn({}, reserves({ enabled: false }))).toBe(false);
    expect(simPlayerChips(row({ squad: "ir", status: "out", out_weeks: 5, rookie: true })).map((c) => c.label)).toEqual(["IR", "ROOKIE"]);
    expect(simPlayerChips(row({ squad: "taxi", status: "out", out_weeks: 1 })).map((c) => c.label)).toEqual(["TAXI"]);
    expect(simPlayerChips(row())).toEqual([]);
    // One injury tag per row: the row's own chip (simDraftRowChips) is the only one; the squad chips never add a second.
    const hurtIr = row({ squad: "ir", status: "out", out_weeks: 7 });
    const all = [...simDraftRowChips(hurtIr), ...simPlayerChips(hurtIr)].map((c) => c.label);
    expect(all.filter((l) => /out/i.test(l))).toEqual(["Out 7w"]);
  });

  it("turns the backend reasons into copy", () => {
    for (const reason of ["ir_full", "ir_ineligible", "taxi_full", "taxi_ineligible", "roster_full"]) {
      const gate = simGameGate({ ok: false, reason });
      expect(gate.kind).toBe("blocked");
      expect(gate.kind === "blocked" && gate.message.length).toBeGreaterThan(10);
    }
  });
});

describe("offseason", () => {
  const off = { stage: "review" as const, season_no: 2, seasons: 5, year: 2028, roster: { size: 18, limit: 16, cuts_needed: 2 } } as never;

  it("steps and the one button per stage", () => {
    expect(simOffseasonSteps("rookie_draft").map((s) => s.state)).toEqual(["done", "current", "todo"]);
    expect(simOffseasonCta(off)).toEqual({ action: "start_rookie_draft", label: "Start rookie draft", blocked: null });
    expect(simOffseasonCta({ ...(off as object), stage: "rookie_draft" } as never).action).toBe("finish_draft");
    const cut = simOffseasonCta({ ...(off as object), stage: "cutdown" } as never);
    expect(cut).toMatchObject({ action: "start_season", label: "Finish cut-down" });
    expect(cut.blocked).toMatch(/Cut 2 players/);
    expect(simOffseasonCta({ ...(off as object), stage: "cutdown", roster: { size: 16, limit: 16, cuts_needed: 0 } } as never).blocked).toBeNull();
    expect(simOffseasonCta({ ...(off as object), stage: "cutdown", roster: { size: 16, limit: 16, cuts_needed: 0 } } as never).label).toBe("Start S3 2028");
    expect(simOffseasonCta(null).action).toBeNull();
  });

  it("describes the clock and your picks", () => {
    const clock = { round: 1, n: 4, pick: "pick:2028:1:3", orig_team_id: "3", orig_team_name: "Me", team_id: "3", team_name: "Me", is_yours: true, traded: false, made: null };
    expect(simRookieClockLine({ on_clock: clock, your_turn: true, total: 48, pick_index: 3 })).toBe("You are on the clock: round 1, pick 4 of 48.");
    expect(simRookieClockLine({ on_clock: { ...clock, team_name: "Rivals" }, your_turn: false, total: 48, pick_index: 3 })).toMatch(/^Rivals is on the clock/);
    expect(simRookieClockLine({ on_clock: null, your_turn: false, total: 48, pick_index: 48 })).toBe("Rookie draft complete.");
  });

  it("shapes the aging report and retirees", () => {
    expect(simMoverText({ delta: -2.34, age_before: 29, age_after: 30, mean_before: 14, mean_after: 11.7 })).toEqual({ arrow: "▼", delta: "-2.3", age: "29 to 30", tone: "danger" });
    expect(simMoverText({ delta: 1.2, age_before: 22, age_after: 23, mean_before: 8, mean_after: 9.2 }).tone).toBe("success");
    expect(simMoverText({ delta: 0.1, age_before: null, age_after: null, mean_before: 8, mean_after: 8.1 })).toMatchObject({ tone: "muted", age: "" });
    const sorted = simRetireesSorted([
      { id: "a", name: "A", pos: "QB", age: 38, is_yours: false },
      { id: "b", name: "B", pos: "RB", age: 33, is_yours: true },
    ]);
    expect(sorted.map((r) => r.id)).toEqual(["b", "a"]);
    expect(simRetireesSorted(null)).toEqual([]);
  });

  it("routes the offseason status and heading", () => {
    expect(simGameStage({ status: "offseason" })).toBe("offseason");
    expect(simWeekHeading({ phase: "offseason", week: 0, round: null, settings: { regular_weeks: 14, playoff_weeks: 3 } as never })).toBe("Offseason");
    expect(simAdvanceLabel({ phase: "offseason", week: 0, settings: {} as never })).toBe("Offseason");
  });

  it("builds endpoint paths", () => {
    const p = simDynastyPaths("g 1");
    expect(p.picks).toBe("/v1/sim/games/g%201/picks");
    expect(p.offseason("QB")).toBe("/v1/sim/games/g%201/offseason?pos=QB");
    expect(p.offseason()).toBe("/v1/sim/games/g%201/offseason");
    expect(p.startSeason).toBe("/v1/sim/games/g%201/offseason/start-season");
  });
});

describe("dynasty summary", () => {
  const archive: SimSeasonArchive = {
    season_no: 1, year: 2026, champion: { team_id: "3", name: "Me", is_you: true },
    you: { rank: 1, wins: 11, losses: 3, ties: 0, pf: 1700.2, seed: 1, playoff_result: "champion", made_playoffs: true, avg_age: 26.1, top_scorers: [{ id: "p", name: "Star", pos: "WR", pts: 250.5 }] },
  };

  it("shapes the summary and survives missing data", () => {
    const view = simDynastySummaryView({
      mode: "dynasty", seasons_total: 5, seasons_played: 2, start_year: 2026, complete: false, titles: 1, playoff_trips: 2, avg_finish: 2.5, wins: 20, losses: 8,
      best_season: { year: 2026, rank: 1, record: "11-3" }, by_year: [{ ...simArchiveToYear(archive) }], picks_held: 6,
    });
    expect(view).toMatchObject({ titlesLine: "1 title", avgFinish: "2.5", bestSeason: "2026: 1st at 11-3", trips: "2 of 2", record: "20-8" });
    expect(view.years[0]).toMatchObject({ year: 2026, finish: "1st", youWon: true, champion: "Me (you)", scorers: "Star 250.5" });
    const empty = simDynastySummaryView(null);
    expect(empty).toMatchObject({ titlesLine: "No titles yet", avgFinish: "-", bestSeason: "-", years: [] });
  });

  it("treats a dynasty result (grade and review null) as render-safe", () => {
    const result = { mode: "dynasty" as const, dynasty: undefined, grade: null, review: null, champion: { team_id: "3", name: "Me" }, final_standings: [], decisions_that_mattered: [] };
    expect(simIsDynastyResult(result)).toBe(true);
    expect(simIsDynastyResult({ grade: { letter: "B" } })).toBe(false);
    expect(normalizeSimResult(result)).toMatchObject({ letter: "", summaryText: "", championName: "Me", decisions: [], mine: null });
  });
});
