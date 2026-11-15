import assert from 'node:assert/strict';
import { describe, it } from 'node:test';

import { buildRecapPage, recapFaab, recapSectionKey, recapWeekChips, recapYourLine, type RecapStoryInput } from "./recapPage.ts";

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
    assert.equal(page.hero.kicker, "Week 9 recap");
    assert.equal(page.hero.headline, "Alpha led the week with 150.2");
    assert.deepEqual(page.hero.stats.map((s) => s.key), ["top", "low", "margin"]);
    assert.equal(page.hero.stats[2].label, "Closest game");
    assert.equal(page.hero.stats[2].value, "0.8");
    assert.deepEqual(page.hero.leader, { team: "Alpha", rosterId: "1", points: "150.2" });
  });

  it("groups stories into one module per kind, in a fixed order, each with a real summary", () => {
    assert.deepEqual(page.sections.map((s) => s.key), ["scoring", "matchups", "waivers", "trades"]);
    for (const section of page.sections) assert.ok(section.parts.map((p) => p.text).join(" ").length > 8);
    assert.ok(page.sections[2].parts[0].text.includes("$14"));
  });

  it("keeps every story reachable", () => {
    assert.equal(page.sections.flatMap((s) => s.stories).length, stories.length);
  });

  it("never invents standings or odds sections", () => {
    assert.equal(recapSectionKey("standings"), "other");
  });
});

describe("recapYourLine", () => {
  it("only speaks about the signed-in team when a story names it", () => {
    assert.equal(recapYourLine(stories, ""), null);
    assert.equal(recapYourLine(stories, "9"), null);
    assert.equal(recapYourLine(stories, "2"), "You lost to Alpha 150.2 to 110.1. You beat Gamma 101.3 to 100.5");
  });
});

describe("week chips and faab", () => {
  it("lists every completed week newest first", () => {
    assert.deepEqual(recapWeekChips(3), [
      { label: "Wk 3", value: "3" },
      { label: "Wk 2", value: "2" },
      { label: "Wk 1", value: "1" },
    ]);
    assert.deepEqual(recapWeekChips(0), []);
  });
  it("reads a FAAB amount", () => {
    assert.equal(recapFaab(story({ metric_value: "$14" })), 14);
    assert.equal(recapFaab(story({ metric_value: "" })), null);
  });
});
