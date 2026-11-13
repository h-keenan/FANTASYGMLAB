import { describe, expect, it } from "vitest";

import type { SimGame, SimWeekRecap } from "./simGame";
import { SIM_FLOW_INITIAL, simFlowReducer, simRecapsFromAdvance, type SimFlowState } from "./simGameFlow";

const game = (status: SimGame["status"], id = "g1"): SimGame =>
  ({ id, status, week: 1, phase: "regular_season", round: null, seed: 1, engine_version: "x", settings: {}, you: null, this_week: null, pending: null, can_trade: true, trade_deadline_week: 10, grade_letter: null, created_at: "", updated_at: "" }) as unknown as SimGame;

const recap = (week: number, season_complete = false): SimWeekRecap =>
  ({ week, kind: "regular", round: null, your_game: null, scores: [], season_complete, champion: null, next_week: week + 1 }) as SimWeekRecap;

const hub: SimFlowState = simFlowReducer(SIM_FLOW_INITIAL, { type: "hub" });

describe("simFlowReducer", () => {
  it("starts loading, then the hub", () => {
    expect(SIM_FLOW_INITIAL.view).toBe("loading");
    expect(hub.view).toBe("hub");
  });

  it("opens a game onto the stage its status implies", () => {
    expect(simFlowReducer(hub, { type: "open", game: game("drafting") })).toMatchObject({ view: "game", gameId: "g1", stage: "draft", tab: "home" });
    expect(simFlowReducer(hub, { type: "open", game: game("in_season") }).stage).toBe("week");
    expect(simFlowReducer(hub, { type: "open", game: game("complete") }).stage).toBe("final");
  });

  it("moves draft -> week when the draft completes", () => {
    const open = simFlowReducer(hub, { type: "open", game: game("drafting") });
    const next = simFlowReducer(open, { type: "game_updated", game: game("in_season") });
    expect(next.stage).toBe("week");
  });

  it("ignores updates for another game", () => {
    const open = simFlowReducer(hub, { type: "open", game: game("in_season") });
    expect(simFlowReducer(open, { type: "game_updated", game: game("complete", "other") })).toBe(open);
  });

  it("a paywall overlays the game and keeps reads working", () => {
    const open = simFlowReducer(hub, { type: "open", game: game("in_season") });
    const paywalled = simFlowReducer(open, { type: "gate", gate: { kind: "premium", upsell: { title: "t", body: "b" }, preview: { weeks_left: 0, paywall_week: 4, paywalled: true } } });
    expect(paywalled.view).toBe("game");
    expect(paywalled.paywall?.upsell?.title).toBe("t");
    expect(simFlowReducer(paywalled, { type: "dismiss_paywall" }).paywall).toBeNull();
  });

  it("unavailable (flag off, storage) takes over the screen", () => {
    expect(simFlowReducer(hub, { type: "gate", gate: { kind: "unavailable", cause: "storage" } })).toMatchObject({ view: "unavailable", cause: "storage" });
    expect(simFlowReducer(SIM_FLOW_INITIAL, { type: "gate", gate: { kind: "unavailable", cause: "off" } })).toMatchObject({ view: "unavailable", cause: "off" });
  });

  it("conflicts do not change the screen; blocked sets a message", () => {
    const open = simFlowReducer(hub, { type: "open", game: game("in_season") });
    expect(simFlowReducer(open, { type: "gate", gate: { kind: "conflict" } })).toBe(open);
    expect(simFlowReducer(open, { type: "gate", gate: { kind: "blocked", reason: "player_taken", message: "Taken" } }).message).toBe("Taken");
  });

  it("an error in a game keeps the game on screen; with no game it is the error view", () => {
    const open = simFlowReducer(hub, { type: "open", game: game("in_season") });
    expect(simFlowReducer(open, { type: "error", message: "x" }).view).toBe("game");
    expect(simFlowReducer(SIM_FLOW_INITIAL, { type: "error", message: "x" }).view).toBe("error");
  });

  it("advance shows recaps, goes back to Home, steps through and closes", () => {
    let s = simFlowReducer(hub, { type: "open", game: game("in_season") });
    s = simFlowReducer(s, { type: "tab", tab: "league" });
    s = simFlowReducer(s, { type: "advanced", recaps: [recap(15), recap(16), recap(17, true)], game: game("complete") });
    expect(s).toMatchObject({ tab: "home", stage: "final", recapIndex: 0 });
    expect(s.recaps).toHaveLength(3);
    s = simFlowReducer(s, { type: "recap_next" });
    s = simFlowReducer(s, { type: "recap_next" });
    expect(s.recapIndex).toBe(2);
    expect(simFlowReducer(s, { type: "recap_next" })).toBe(s);
    expect(simFlowReducer(s, { type: "recap_close" }).recaps).toEqual([]);
  });

  it("setup, deleted and tab are simple", () => {
    expect(simFlowReducer(hub, { type: "setup" }).view).toBe("setup");
    const open = simFlowReducer(hub, { type: "open", game: game("in_season") });
    expect(simFlowReducer(open, { type: "deleted" })).toMatchObject({ view: "hub", gameId: null });
    expect(simFlowReducer(open, { type: "tab", tab: "home" })).toBe(open);
    expect(simFlowReducer(open, { type: "tab", tab: "team" }).tab).toBe("team");
  });
});

describe("simRecapsFromAdvance", () => {
  it("returns the played week then any playoff weeks, or nothing", () => {
    expect(simRecapsFromAdvance(undefined, [recap(2)])).toEqual([]);
    expect(simRecapsFromAdvance(recap(15), undefined).map((r) => r.week)).toEqual([15]);
    expect(simRecapsFromAdvance(recap(15), [recap(16), recap(17)]).map((r) => r.week)).toEqual([15, 16, 17]);
  });
});
