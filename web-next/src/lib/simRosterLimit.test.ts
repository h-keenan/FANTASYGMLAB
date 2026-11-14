import { describe, expect, it } from "vitest";

import { simAdvanceBlockers, simGameReasonMessage, simLimitBlocks, simOffseasonCta, simOverLimitNote } from "./simGame";
import { simAdvanceState, simTradeFit } from "./simLayout";

const game = (pending: Record<string, unknown>) => ({ pending: { claims: 0, inbox: 0, lineup_warnings: 0, roster_size: 23, roster_limit: 18, cuts_needed: 5, ...pending } }) as never;

describe("soft roster limit (limit_blocks false): over the limit never blocks advancing", () => {
  it("an old save or an old server (limit_blocks absent or true) still blocks", () => {
    expect(simLimitBlocks({ cuts_needed: 5 } as never)).toBe(true);
    expect(simAdvanceState({ week: 3, pending: { cuts_needed: 5 } }, 0).blocked).toBe(true);
    expect(simAdvanceBlockers(game({}))).toEqual([expect.objectContaining({ code: "cuts" })]);
  });
  it("a soft-limit save is never blocked: Advance and the blocker list ignore the overage", () => {
    expect(simLimitBlocks({ limit_blocks: false })).toBe(false);
    const state = simAdvanceState({ week: 3, pending: { cuts_needed: 5, limit_blocks: false } }, 0);
    expect(state.blocked).toBe(false);
    expect(simAdvanceBlockers(game({ limit_blocks: false }))).toEqual([]);
  });
  it("the offseason button reads Start season with a note instead of Finish cut-down", () => {
    const off = { stage: "cutdown", season_no: 1, roster: { size: 23, limit: 18, cuts_needed: 5, limit_blocks: false } } as never;
    expect(simOffseasonCta(off)).toEqual({ action: "start_season", label: "Start season 2", blocked: null, note: "Over the limit by 5: cut or trade to add players." });
    const old = simOffseasonCta({ stage: "cutdown", season_no: 1, roster: { size: 23, limit: 18, cuts_needed: 5 } } as never);
    expect(old.label).toBe("Finish cut-down");
    expect(old.blocked).toContain("Cut 5 players");
  });
  it("copy for the add-while-over error and the note", () => {
    expect(simOverLimitNote(3)).toBe("Over the limit by 3: cut or trade to add players.");
    expect(simGameReasonMessage("roster_full", { over_by: 3 })).toBe(simOverLimitNote(3));
    expect(simGameReasonMessage("roster_full")).toContain("full");
  });
});

describe("trade builder roster count agrees with the server rule", () => {
  // Server (game_actions.check_roster_room): after = active kept + non-pick incoming; blocked when after > limit and after > current.
  it("active-only count, blocked only when it adds past the limit", () => {
    expect(simTradeFit(18, 18, 1, 2, true)).toMatchObject({ after: 19, over: 1, blocked: true }); // at the limit, adding: blocked
    expect(simTradeFit(23, 18, 2, 2, true)).toMatchObject({ after: 23, over: 5, blocked: false }); // over, even swap: fine
    expect(simTradeFit(23, 18, 3, 1, true)).toMatchObject({ after: 21, blocked: false }); // over, shedding: fine
    expect(simTradeFit(23, 18, 1, 2, true).blocked).toBe(true); // over, adding: blocked
    expect(simTradeFit(16, 18, 1, 3, true)).toMatchObject({ after: 18, room: 0, blocked: false }); // lands exactly at the limit
    expect(simTradeFit(18, 18, 1, 2).blocked).toBe(false); // an old save never blocks the trade
  });
});
