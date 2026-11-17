import { describe, expect, it } from "vitest";

import { basicSummary, calibrationNote, compareLine, tradePointsLine, type TrackAdvancedView, type TrackHit } from "./trackRecordView";

const hit = (over: Partial<TrackHit> = {}): TrackHit => ({ n: 12, right: 9, wrong: 3, hit_rate: 0.75, mean_edge_pts: 10, reliability: "solid", ...over });

function adv(over: Partial<TrackAdvancedView> = {}): TrackAdvancedView {
  const bucket = { ...hit(), supported: true };
  return {
    advice: hit(),
    own_calls: hit({ n: 6 }),
    compare: { verdict: "advice_ahead", diff_pts: 12 },
    calibration: { high: bucket, medium: { ...bucket, supported: false }, low: { ...bucket, supported: false } },
    ...over,
  };
}

describe("trackRecordView", () => {
  it("words a per-trade points line only from a real production number", () => {
    expect(tradePointsLine({ status: "ready", production: { net_points_ppr: 34.4, weeks_counted: 4 } })).toBe("This trade: +34 pts for you so far over 4 wks");
    expect(tradePointsLine({ status: "ready", production: { net_points_ppr: -12, weeks_counted: 1 } })).toBe("This trade: -12 pts for you so far over 1 wk");
    expect(tradePointsLine({ status: "insufficient_data" })).toBeNull();
    expect(tradePointsLine(null)).toBeNull();
  });

  it("never states a rate when the sample is too small", () => {
    expect(basicSummary({ trades_confirmed: 2, trades_graded: 0, worked_out: 0, didnt_pan_out: 0, net_points_total: 0, reliability: "too_early" })).toEqual(["2 confirmed trades", "results still coming in"]);
    expect(basicSummary({ trades_confirmed: 3, trades_graded: 3, worked_out: 2, didnt_pan_out: 1, net_points_total: 20, reliability: "too_early" })).toContain("too early to read");
  });

  it("calibrates only supported buckets", () => {
    expect(calibrationNote("High", adv())).toContain("held up 9 of 12");
    expect(calibrationNote("Medium", adv())).toBeNull();
    const weak = adv();
    weak.calibration.high = { ...hit({ right: 4, wrong: 8, hit_rate: 0.33 }), supported: true };
    expect(calibrationNote("high", weak)).toContain("weigh it lighter");
    expect(calibrationNote("high", null)).toBeNull();
  });

  it("calls a small gap luck, not skill", () => {
    expect(compareLine(adv({ compare: { verdict: "within_noise", diff_pts: 3 } }))).toContain("within noise");
    expect(compareLine(adv({ compare: { verdict: "too_early" } }))).toContain("Need at least 5");
  });
});
