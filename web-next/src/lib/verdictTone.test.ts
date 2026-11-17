import { describe, expect, it } from "vitest";

import { bandCompactTone, bandSimTone, bandToken, deltaBand, percentBand, probabilityBand, verdictBand } from "./verdictTone";
import { bandColorVar, percentColorVar, verdictColorVar } from "./verdictToneCss";
import { simOddsTone } from "./simPresentation.ts";
import { simWinChanceTone as gameTone } from "./simGame";
import { statusRingTone } from "./statusHeader";
import { matchupVerdict } from "./matchupPresentation";
import { insightsParts } from "./matchupModules";

describe("probabilityBand", () => {
  it("bands a probability at the shared cut points", () => {
    expect(probabilityBand(0.9)).toBe("good");
    expect(probabilityBand(0.6)).toBe("good");
    expect(probabilityBand(0.59)).toBe("neutral");
    expect(probabilityBand(0.4)).toBe("neutral");
    expect(probabilityBand(0.39)).toBe("caution");
    expect(probabilityBand(0.2)).toBe("caution");
    expect(probabilityBand(0.03)).toBe("bad");
  });
  it("reads missing or non-finite as neutral", () => {
    expect(probabilityBand(null)).toBe("neutral");
    expect(probabilityBand(undefined)).toBe("neutral");
    expect(probabilityBand(Number.NaN)).toBe("neutral");
  });
  it("percentBand is the same map on 0..100", () => {
    for (const pct of [0, 3, 20, 39, 40, 59, 60, 100]) expect(percentBand(pct)).toBe(probabilityBand(pct / 100));
  });
});

describe("the same % has the same colour on every page", () => {
  it("60% is good everywhere (the audit's green-vs-gold split)", () => {
    expect(percentColorVar(60)).toBe("var(--color-success)");
    expect(simOddsTone(0.6)).toBe("success");
    expect(gameTone(0.6)).toBe("success");
    expect(statusRingTone(60)).toBe("success");
  });
  it("21% and 3% share one answer across pages", () => {
    expect(simOddsTone(0.21)).toBe("warning");
    expect(gameTone(0.21)).toBe("warning");
    expect(statusRingTone(21)).toBe("warning");
    expect(simOddsTone(0.03)).toBe("danger");
    expect(statusRingTone(3)).toBe("danger");
  });
});

describe("verdictBand and helpers", () => {
  it("maps verdict words", () => {
    expect(verdictBand("accept")).toBe("good");
    expect(verdictBand("decline")).toBe("bad");
    expect(verdictBand("counter")).toBe("caution");
    expect(verdictBand("fair")).toBe("neutral");
    expect(verdictBand("negative")).toBe("bad");
    expect(verdictBand(null)).toBe("neutral");
  });
  it("a negative delta is muted, never bad", () => {
    expect(deltaBand(3)).toBe("good");
    expect(deltaBand(-14.6)).toBe("neutral");
    expect(deltaBand(0)).toBe("neutral");
  });
  it("converts to tokens, css vars and tones", () => {
    expect(bandToken("bad")).toBe("danger");
    expect(bandColorVar("neutral")).toBe("var(--color-text-secondary)");
    expect(verdictColorVar("decline")).toBe("var(--color-danger)");
    expect(bandCompactTone("neutral")).toBe("muted");
    expect(bandSimTone("neutral")).toBe("accent");
  });
});

describe("verdict sentences are neutral text", () => {
  it("the opponent-favored headline carries no tone in the summary line", () => {
    const matchup = { game_state: "pre", win_probability: { available: true, probability: 0.03 } } as never;
    const verdict = matchupVerdict(matchup);
    expect(verdict.headline).toBe("Your opponent is favored.");
    const parts = insightsParts(verdict.headline, [{ position: "QB", edge: 8.8 }, { position: "TE", edge: -14.6 }]);
    expect(parts[0].tone).toBeUndefined();
    expect(parts.some((p) => p.tone === "danger")).toBe(false);
  });
});
