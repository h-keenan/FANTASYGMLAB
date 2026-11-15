import { describe, expect, it } from "vitest";

import { buildRecapPage, recapFaab, recapSectionKey, recapWeekChips, recapYourLine, type RecapStoryInput } from "./recapPage";

function story(over: Partial<RecapStoryInput>): RecapStoryInput {
  return { story_type: "performance", title: "t", summary: "s", primary_team: "Alpha", secondary_team: "", primary_roster_id: "1", secondary_roster_id: "", players: [], metric_label: "Points", metric_value: "150.2", ...over };
}

const stories: RecapStoryInput[] = [
  story({ story_type: "performance" }),
  story({ story_type: "performance_low", primary_team: "Gamma", primary_roster_id: "3", metric_value: "57.9" }),
  story({ story_type: "matchup", primary_team: "Alpha", secondary_team: "Beta", secondary_roster_id: "2", metric_label: "Margin", metric_value: "40.1", winner_points: 150.2, loser_points: 110.1 }),
  story({ story_type: "matchup_close", primary_team: "Beta", primary_roster_id: "2", secondary_team: "Gamma", secondary_roster_id: "3", metric_label: "Margin", metric_value: "0.8", winner_points: 101.3, loser_points: 100.5 }),
  story({ story_type: "waiver", metric_label: "FAAB", metric_value: "$14", players: ["Breakout WR"] }),
  story({ story_type: "trade", primary_team: "Alpha", secondary_team: "Beta", secondary_roster_id: "2" }),
];

describe("buildRecapPage", () => {
  const page = buildRecapPage({ week: 9, headline: "League memory", stories, incomplete: false });

  it("states the week's result once, from the recorded leader", () => {
    expect(page.hero.kicker).toBe("Week 9 recap");
    expect(page.hero.headline).toBe("Alpha led the week with 150.2");
    expect(page.hero.stats.map((s) => s.key)).toEqual(["top", "low", "margin"]);
    expect(page.hero.stats[2]).toMatchObject({ label: "Closest game", value: "0.8" });
    expect(page.hero.leader).toEqual({ team: "Alpha", rosterId: "1", points: "150.2" });
  });

  it("groups stories into one module per kind, in a fixed order, each with a real summary", () => {
    expect(page.sections.map((s) => s.key)).toEqual(["scoring", "matchups", "waivers", "trades"]);
    for (const section of page.sections) expect(section.parts.map((p) => p.text).join(" ").length).toBeGreaterThan(8);
    expect(page.sections[2].parts[0].text).toContain("$14");
  });

  it("keeps every story reachable", () => {
    expect(page.sections.flatMap((s) => s.stories)).toHaveLength(stories.length);
  });

  it("never invents standings or odds sections", () => {
    expect(recapSectionKey("standings")).toBe("other");
  });
});

describe("recapYourLine", () => {
  it("only speaks about the signed-in team when a story names it", () => {
    expect(recapYourLine(stories, "")).toBeNull();
    expect(recapYourLine(stories, "9")).toBeNull();
    expect(recapYourLine(stories, "2")).toBe("You lost to Alpha 150.2 to 110.1. You beat Gamma 101.3 to 100.5");
  });
});

describe("week chips and faab", () => {
  it("lists every completed week newest first", () => {
    expect(recapWeekChips(3)).toEqual([
      { label: "Wk 3", value: "3" },
      { label: "Wk 2", value: "2" },
      { label: "Wk 1", value: "1" },
    ]);
    expect(recapWeekChips(0)).toEqual([]);
  });
  it("reads a FAAB amount", () => {
    expect(recapFaab(story({ metric_value: "$14" }))).toBe(14);
    expect(recapFaab(story({ metric_value: "" }))).toBeNull();
  });
});
