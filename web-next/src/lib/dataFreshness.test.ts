import { describe, expect, it } from "vitest";

import { freshnessAsOf, freshnessLabel, freshnessText } from "./dataFreshness";

const NOW = new Date(2026, 10, 19, 12, 0, 0).getTime();
const secs = (d: Date) => d.getTime() / 1000;

describe("freshnessText", () => {
  it("says how long ago for values", () => {
    expect(freshnessText("values", secs(new Date(2026, 10, 19, 10, 0)), NOW)).toBe("Values as of 2h ago");
    expect(freshnessText("values", secs(new Date(2026, 10, 19, 11, 40)), NOW)).toBe("Values as of 20m ago");
    expect(freshnessText("values", NOW / 1000, NOW)).toBe("Values as of just now");
  });

  it("uses the clock for injuries and prospects", () => {
    expect(freshnessText("injuries", secs(new Date(2026, 10, 19, 9, 40)), NOW)).toBe("Injuries updated 9:40am");
    expect(freshnessText("injuries", secs(new Date(2026, 10, 19, 0, 5)), NOW)).toBe("Injuries updated 12:05am");
    expect(freshnessText("injuries", secs(new Date(2026, 10, 18, 21, 15)), NOW)).toBe("Injuries updated yesterday 9:15pm (may be behind)");
    expect(freshnessText("prospects", secs(new Date(2026, 10, 12, 9, 0)), NOW)).toBe("Prospects updated Nov 12");
  });

  it("adds a plain 'may be behind' past the threshold, never anything alarming", () => {
    const text = freshnessText("values", secs(new Date(2026, 10, 17, 12, 0)), NOW);
    expect(text).toBe("Values as of 2d ago (may be behind)");
    expect(text).not.toMatch(/error|fail|stale|wrong/i);
    expect(freshnessText("injuries", secs(new Date(2026, 10, 18, 21, 0)), NOW)).toBe("Injuries updated yesterday 9:00pm (may be behind)");
  });
});

describe("freshnessAsOf / freshnessLabel", () => {
  const report = {
    datasets: [
      { name: "values_fantasycalc", as_of: secs(new Date(2026, 10, 19, 10, 0)), as_of_source: "fetch_timestamp" },
      { name: "players_db_and_injury_status", as_of: secs(new Date(2026, 10, 19, 9, 40)) },
      { name: "adp_rookie_dynasty", as_of: null },
    ],
  };

  it("labels datasets the report can vouch for", () => {
    expect(freshnessLabel(report, "values", NOW)).toBe("Values as of 2h ago");
    expect(freshnessLabel(report, "injuries", NOW)).toBe("Injuries updated 9:40am");
  });

  it("returns nothing for a null as_of, a missing row or no report", () => {
    expect(freshnessLabel(report, "adp", NOW)).toBeNull();
    expect(freshnessLabel(report, "schedule", NOW)).toBeNull();
    expect(freshnessLabel(null, "values", NOW)).toBeNull();
    expect(freshnessLabel({}, "values", NOW)).toBeNull();
  });

  it("never trusts a values timestamp that is only a file mtime", () => {
    const mtime = { datasets: [{ name: "values_fantasycalc", as_of: secs(new Date(2026, 10, 19, 11, 55)), as_of_source: "file_mtime" }] };
    expect(freshnessAsOf(mtime, "values")).toBeNull();
    expect(freshnessAsOf({ datasets: [{ name: "values_fantasycalc", as_of: 5 }] }, "values")).toBeNull();
  });
});
