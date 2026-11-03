import { describe, expect, it } from "vitest";

import type { AlertItem, HistoryTransaction } from "./api";
import { NEW_VISIT_GAP_MS, advanceLastVisit, buildSinceItems, parseLastVisit } from "./sinceLastVisit";

const HOUR = 3_600_000;

const tx = (type: HistoryTransaction["type"], timestamp: number): HistoryTransaction =>
  ({ transaction_id: `${type}-${timestamp}`, season: "2026", league_id: "L", week: 8, timestamp, type, draft_picks: [], sides: [], grade: null }) as HistoryTransaction;
const alert = (published_ts: number | null, event_type = "injury/status"): AlertItem =>
  ({ title: "t", link: null, source: null, summary: null, published_ts, event_type, speculative: false, alert_key: `${published_ts}`, read: false }) as AlertItem;

describe("advanceLastVisit", () => {
  it("starts the clock on a first visit and shows nothing", () => {
    const { next, display } = advanceLastVisit(null, 1_000_000);
    expect(display).toBeNull();
    expect(next).toEqual({ since: 1_000_000, last: 1_000_000 });
  });

  it("keeps the baseline for a refresh in the same sitting", () => {
    const prev = { since: 100, last: 5_000_000 };
    const { next, display } = advanceLastVisit(prev, 5_000_000 + NEW_VISIT_GAP_MS - 1);
    expect(next.since).toBe(100);
    expect(display).toBeGreaterThanOrEqual(100);
  });

  it("moves the baseline to the previous visit after a real gap", () => {
    const now = 100 * HOUR;
    const { next, display } = advanceLastVisit({ since: 1, last: 90 * HOUR }, now);
    expect(next).toEqual({ since: 90 * HOUR, last: now });
    expect(display).toBe(90 * HOUR);
  });

  it("caps a very long absence at 14 days", () => {
    const now = 100 * 24 * HOUR;
    const { display } = advanceLastVisit({ since: 1, last: 2 }, now);
    expect(display).toBe(now - 14 * 24 * HOUR);
  });
});

describe("parseLastVisit", () => {
  it("rejects missing or malformed values", () => {
    expect(parseLastVisit(null)).toBeNull();
    expect(parseLastVisit("nope")).toBeNull();
    expect(parseLastVisit('{"since":"x"}')).toBeNull();
    expect(parseLastVisit('{"since":5,"last":9}')).toEqual({ since: 5, last: 9 });
  });
});

describe("buildSinceItems (real data only)", () => {
  const since = 1_700_000_000_000;
  it("counts trades, waiver/free-agent activity and news after the baseline, in the right units", () => {
    const items = buildSinceItems({
      sinceMs: since,
      transactions: [tx("trade", since + 5), tx("trade", since - 5), tx("waiver", since + 9), tx("free_agent", Math.floor(since / 1000) + 2)],
      alerts: [alert((since + 1000) / 1000), alert((since - 1000) / 1000), alert((since + 2000) / 1000, "role/depth chart")],
    });
    expect(items.map((i) => [i.key, i.value])).toEqual([
      ["trades", "1 trade in your league"],
      ["claims", "2 adds and claims in your league"],
      ["news", "2 updates, 1 injury/status"],
    ]);
  });

  it("returns nothing when nothing changed", () => {
    expect(buildSinceItems({ sinceMs: since, transactions: [tx("trade", since - 1)], alerts: [alert(null)] })).toEqual([]);
  });
});
