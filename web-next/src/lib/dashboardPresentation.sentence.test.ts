import { describe, expect, it } from "vitest";

import type { BriefingItem } from "@/lib/api";
import { firstSentence, watchSummary, watchTag, watchTitle } from "@/lib/dashboardPresentation";

const base = {
  category: "watch",
  headline: "",
  reason: "",
  supporting_context: null,
  destination: "alerts",
  route_player_id: "",
  route_player_name: "",
  route_player_position: "",
  route_player_team: "",
  route_player_tier: "",
  route_player_score: null,
  route_player_injury_status: "",
  mentioned_players: [],
  recommendation_narrative: null,
  presentation: null,
  recommendation_id: "r",
  tier_label: "",
} as BriefingItem;

describe("watch row sentences", () => {
  it("keeps only the first sentence and drops raw feed tails", () => {
    expect(firstSentence("Jalen Hurts (QB) - starter | Brashard Smith (RB) - bench")).toBe("Jalen Hurts (QB) - starter");
    expect(firstSentence("Monitor Gardner Minshew II. A same-team QB teammate is rising. More.")).toBe(
      "Monitor Gardner Minshew II. A same-team QB teammate is rising.",
    );
    expect(firstSentence("Starter is out. Replace him.")).toBe("Starter is out.");
  });

  it("builds sentences from structured fields", () => {
    expect(watchSummary({ ...base, route_player_injury_status: "IR", reason: "Jalen Hurts (QB) - starter | x" })).toBe(
      "Listed as IR; check your lineup.",
    );
    expect(watchSummary({ ...base, reason: "Usage down 24% (high confidence) over 3 weeks." })).toBe("Usage is down 24% recently.");
  });

  it("never titles a row with a bare position", () => {
    expect(watchTitle({ ...base, headline: "RB" })).toBe("RB room");
    expect(watchTitle({ ...base, headline: "Handcuff watch" })).toBe("Handcuff watch");
  });
});

describe("watchTag trending direction", () => {
  const base = { category: "value_trend", reason: "", supporting_context: "" } as unknown as BriefingItem;
  it("colors trending up positive and usage drops negative", () => {
    expect(watchTag({ ...base, headline: "Taylor is trending up" }).color).toBe("var(--text-positive)");
    expect(watchTag({ ...base, headline: "Morgan is losing usage", reason: "Usage down 31%." }).color).toBe("var(--text-negative)");
  });
});
