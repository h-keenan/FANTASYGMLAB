import { describe, expect, it } from "vitest";

import { bandCompactTone, bandSimTone, bandToken, deltaBand, percentBand, percentWord, probabilityBand, probabilityWord, toneToken, verdictBand } from "./verdictTone";
import { toneColorVar } from "./verdictToneCss";
import { bandColorVar, percentColorVar, verdictColorVar } from "./verdictToneCss";
import { simHeadline, simOddsTone } from "./simPresentation.ts";
import { simWinChanceTone as gameTone } from "./simGame";
import { statusRingTone } from "./statusHeader";
import { matchupVerdict } from "./matchupPresentation";
import { insightsParts, marginNowLabel, matchupCardModel } from "./matchupModules";

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

describe("label and percentage come from one source", () => {
  it("probabilityWord follows the same bands as the colour", () => {
    expect(probabilityWord(0.57)).toBe("Toss-up");
    expect(probabilityWord(0.6)).toBe("Favored");
    expect(probabilityWord(0.4)).toBe("Toss-up");
    expect(probabilityWord(0.39)).toBe("Underdog");
    expect(probabilityWord(0.1)).toBe("Long shot");
    expect(probabilityWord(null)).toBe("");
    for (const pct of [3, 20, 39, 40, 57, 59, 60, 100]) {
      const band = percentBand(pct);
      expect(percentWord(pct) === "Favored").toBe(band === "good");
      expect(percentWord(pct) === "Toss-up").toBe(band === "neutral");
    }
  });
  it("the Matchup chip carries the percentage and the word of the same band", () => {
    const model = (winPercent: number) =>
      matchupCardModel({ week: 10, live: false, final: false, myName: "You", opponentName: "Opp", myScore: null, opponentScore: null, myProjected: 118.3, opponentProjected: 109.7, winPercent, kickedOff: false, playersLeft: null, swing: [] });
    expect(model(57).win?.label).toBe("57% win · Toss-up");
    expect(model(62).win?.label).toBe("62% win · Favored");
    expect(model(30).win?.label).toBe("30% win · Underdog");
  });
  it("the lineup margin badge names its basis, so Even never contradicts a win chance", () => {
    expect(marginNowLabel(0, "0.0")).toBe("Even now");
    expect(marginNowLabel(3.2, "+3.2")).toBe("+3.2 now");
  });
  it("the sim playoff sentence cuts at the same 40% edge as the band", () => {
    const f = (playoffs: number) => simHeadline({ odds: { playoffs, title: 0.04, playoff_spots: 6 } } as never);
    expect(f(0.4)).toMatch(/coin flip/);
    expect(f(0.39)).not.toMatch(/coin flip/);
    expect(f(0.6)).toMatch(/good shape/);
  });
});

describe("toneToken", () => {
  it("maps positive green/accent and risk amber, never red", () => {
    expect(toneToken("success")).toBe("success");
    expect(toneToken("positive")).toBe("accent");
    expect(toneToken("accent")).toBe("accent");
    expect(toneToken("risk")).toBe("warning");
    expect(toneToken("warning")).toBe("warning");
    expect(toneToken("danger")).toBe("warning");
    expect(toneToken("pending")).toBe("muted");
    expect(toneToken(undefined)).toBe("muted");
  });
  it("never yields a danger css colour for any tone", () => {
    for (const t of ["success", "positive", "accent", "risk", "warning", "danger", "bad", "decline", "pending", "x", null])
      expect(toneColorVar(t)).not.toContain("danger");
    expect(toneColorVar("risk")).toBe("var(--color-warning)");
    expect(toneColorVar("pending")).toBe("var(--color-text-muted)");
  });
});
