import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TradeHubContent } from "./TradeHubContent";
import type { TradeHubResponse } from "@/lib/api";
import { BEGINNER_HELP, experienceCopy } from "@/lib/experienceCopy";

vi.mock("@/context/ExperienceLevelContext", () => ({
  useExperienceCopy: () => experienceCopy("beginner"),
}));

const DATA: TradeHubResponse = {
  ok: true,
  reason: "",
  ideas: [],
  entitlement: null,
  team_strategy: "contender",
  posture_sentence: "You're competing now, so ideas favor current value.",
  hold: {
    verdict: "hold",
    reason: "no_ideas",
    headline: "Holding is the best move right now.",
    why: [{ factor: "ideas", text: "No trade idea fit your roster and your league's rosters today." }],
    ideas_optional: false,
  },
};

describe("TradeHubContent for a beginner", () => {
  it("explains the posture term and what holding means", () => {
    render(<TradeHubContent leagueId="1" leagueName="L" data={DATA} />);

    expect(screen.getByText("You're competing now, so ideas favor current value.")).toBeInTheDocument();
    expect(screen.getByText(BEGINNER_HELP.tradeHubPosture)).toBeInTheDocument();
    expect(screen.getByText(BEGINNER_HELP.tradeHubHold)).toBeInTheDocument();
  });
});
