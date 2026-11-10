import { describe, expect, it } from "vitest";

import type { RankedPlayer } from "@/lib/api";
import { mergeSearchMatches } from "@/lib/leaguePlayerSearch";

const p = (id: string) => ({ player_id: id, name: id }) as unknown as RankedPlayer;

describe("mergeSearchMatches", () => {
  it("appends server matches missing from the window, keeping window order", () => {
    const merged = mergeSearchMatches([p("1"), p("2")], [p("2"), p("650")]);
    expect(merged.map((x) => x.player_id)).toEqual(["1", "2", "650"]);
  });
  it("returns the same array when nothing is new", () => {
    const pool = [p("1")];
    expect(mergeSearchMatches(pool, [p("1")])).toBe(pool);
    expect(mergeSearchMatches(pool, [])).toBe(pool);
  });
});
