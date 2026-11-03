import { describe, expect, it } from "vitest";

import type { NewsItem } from "./api";
import { appendNewsPage, groupNewsByDay, newsDayLabel } from "./newsPresentation";

const NOW = new Date(2026, 9, 28, 15, 0, 0).getTime();
const at = (d: Date) => d.getTime() / 1000;
const item = (title: string, ts: number | null): NewsItem => ({
  title,
  link: `https://x/${title}`,
  source: "ESPN",
  summary: null,
  published_ts: ts,
  event_type: null,
  speculative: false,
});

describe("newsDayLabel / groupNewsByDay", () => {
  it("labels today, yesterday and older calendar days", () => {
    expect(newsDayLabel(at(new Date(2026, 9, 28, 1)), NOW)).toBe("Today");
    expect(newsDayLabel(at(new Date(2026, 9, 27, 23)), NOW)).toBe("Yesterday");
    expect(newsDayLabel(at(new Date(2026, 9, 20, 9)), NOW)).toBe("Tue, Oct 20");
    expect(newsDayLabel(at(new Date(2025, 11, 2, 9)), NOW)).toContain("2025");
    expect(newsDayLabel(null, NOW)).toBe("Earlier");
  });

  it("groups a newest-first list by day, keeping order", () => {
    const sections = groupNewsByDay(
      [item("a", at(new Date(2026, 9, 28, 9))), item("b", at(new Date(2026, 9, 28, 2))), item("c", at(new Date(2026, 9, 20)))],
      NOW,
    );
    expect(sections.map((s) => [s.label, s.items.map((i) => i.title)])).toEqual([
      ["Today", ["a", "b"]],
      ["Tue, Oct 20", ["c"]],
    ]);
  });
});

describe("appendNewsPage", () => {
  it("skips stories already shown", () => {
    const merged = appendNewsPage([item("a", 1), item("b", 2)], [item("b", 2), item("c", 3)]);
    expect(merged.map((i) => i.title)).toEqual(["a", "b", "c"]);
  });
});
