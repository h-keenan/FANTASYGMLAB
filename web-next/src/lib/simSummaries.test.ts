import { describe, expect, it } from "vitest";

import { compactSummaryText } from "./compactModule";
import { simInboxParts, simInjuryParts, simLeagueParts, simWaiverParts } from "./simSummaries";

describe("sim home summaries: a collapsed module is a status line, never an empty header", () => {
  it("trade inbox", () => {
    expect(compactSummaryText(simInboxParts({ count: 0, items: [] }))).toBe("No offers waiting");
    expect(compactSummaryText(simInboxParts({ count: 2, items: [{ from: { name: "Rivals" }, expires_week: 4 }] }))).toBe("2 offers · from Rivals · expires wk 4");
  });
  it("waiver targets", () => {
    expect(compactSummaryText(simWaiverParts([]))).toBe("Nothing beats your roster");
    expect(compactSummaryText(simWaiverParts([{ player: { name: "Rory Runner" }, gain_now: 3.2, gain_ros: 1 }]))).toBe("1 target · top: Runner · +3.2 pts");
  });
  it("injuries", () => {
    expect(compactSummaryText(simInjuryParts([]))).toBe("Everyone is healthy");
    expect(compactSummaryText(simInjuryParts([{ starting: true, player: { name: "Jalen Hurts" } }]))).toBe("1 out · 1 starting · Hurts");
  });
  it("league section carries rank, playoff status and moves", () => {
    const standings = { in_playoffs: true, rows: [{ is_you: true, rank: 3, wins: 4, losses: 1 }] };
    expect(compactSummaryText(simLeagueParts(standings, 5, { hot: 2, cold: 1 }))).toBe("#3 · In · 2 hot · 1 cold · 5 moves");
  });
});
