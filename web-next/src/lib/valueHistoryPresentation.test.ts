import { describe, expect, it } from "vitest";

import { formatRatingDelta, ratingHistoryCaption, shortDate, signalReason, signalsStatusMessage } from "@/lib/valueHistoryPresentation";

describe("valueHistoryPresentation", () => {
  it("formats dates without timezone drift", () => {
    expect(shortDate("2026-10-12")).toBe("Oct 12");
    expect(shortDate(null)).toBe("");
    expect(formatRatingDelta(4)).toBe("+4");
    expect(formatRatingDelta(-2)).toBe("-2");
  });

  it("states the real span and only the changes the data supports", () => {
    const caption = ratingHistoryCaption({
      status: "ok",
      points: [
        { date: "2026-10-01", rating: 60 },
        { date: "2026-10-09", rating: 66 },
      ],
      span_days: 8,
      changes: [{ days: 8, delta: 6 }],
    })!;
    expect(caption.chart).toBe(true);
    expect(caption.text).toContain("2 daily snapshots, Oct 1 to Oct 9 (8 days of history)");
    expect(caption.changes).toEqual(["+6 over 8 days"]);
  });

  it("does not draw a chart for a short history and hides when unavailable", () => {
    const one = ratingHistoryCaption({ status: "insufficient_history", points: [{ date: "2026-10-01", rating: 60 }], span_days: 0, first_date: "2026-10-01" })!;
    expect(one.chart).toBe(false);
    expect(one.text).toContain("started Oct 1");
    expect(ratingHistoryCaption({ status: "unavailable", points: [], span_days: 0 })).toBeNull();
    expect(ratingHistoryCaption(null)).toBeNull();
  });

  it("names both halves of a signal and the real span while history builds", () => {
    expect(
      signalReason({ rating_change: -6, production_percentile: 80, value_percentile: 50, signal: "buy_low", position: "WR" }),
    ).toBe("Value -6, production 80th pct vs value 50th among WRs");
    expect(signalsStatusMessage({ status: "history_building", span_days: 3, min_span_days: 7 })).toContain("3 days stored so far, 7 needed");
    expect(signalsStatusMessage({ status: "ok" })).toBeNull();
  });
});
