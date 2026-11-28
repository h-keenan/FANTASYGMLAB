import { describe, expect, it } from "vitest";
import { isPickAsset, tradeOutcomeChips, tradeValueDelta, tradeVerdictBadge } from "./tradeOutcomeChips";

describe("tradeOutcomeChips", () => {
  it("gain is a success chip, loss is muted (never red)", () => {
    expect(tradeOutcomeChips({ outcomeLabel: "Made it", netPts: 34 })[0]).toMatchObject({ label: "You gained +34", tone: "success" });
    const loss = tradeOutcomeChips({ outcomeLabel: "Made it", netPts: -12 });
    expect(loss[0]).toMatchObject({ label: "Down 12", tone: "muted" });
  });
  it("falls back to the outcome label without points", () => {
    expect(tradeOutcomeChips({ outcomeLabel: "Didn't send", netPts: null })).toEqual([{ key: "outcome", label: "Didn't send", tone: "muted" }]);
  });
  it("the value trend moved out of the chips into the single delta number", () => {
    expect(tradeOutcomeChips({ outcomeLabel: "Made it", netPts: 34 }).map((c) => c.key)).toEqual(["pts"]);
    expect(tradeValueDelta(12)).toEqual({ label: "+12%", tone: "success" });
    expect(tradeValueDelta(-4)).toEqual({ label: "-4%", tone: "muted" });
    expect(tradeValueDelta(0.2)).toBeNull();
    expect(tradeValueDelta(null)).toBeNull();
  });
  it("only a worked-out verdict is green; nothing is red", () => {
    expect(tradeVerdictBadge("worked_out", "Worked out")).toEqual({ key: "verdict", label: "Worked out", tone: "success" });
    expect(tradeVerdictBadge("didnt_pan_out", "Didn't pan out")?.tone).toBe("muted");
    expect(tradeVerdictBadge(null, "x")).toBeNull();
  });
  it("detects pick assets", () => {
    expect(isPickAsset({ name: "2027 Round 1", position: "" })).toBe(true);
    expect(isPickAsset({ name: "2026 1st Round Pick", position: "PICK" })).toBe(true);
    expect(isPickAsset({ name: "Test Sender", position: "WR", player_id: "100" })).toBe(false);
    expect(isPickAsset({ name: "Test Sender", position: "WR" })).toBe(false);
  });
});
