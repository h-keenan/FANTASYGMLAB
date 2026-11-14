import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SeasonReviewSections } from "./SeasonReviewSections";
import { buildSimReviewSections } from "@/lib/simReview";

const player = { id: "g1", name: "Jalen Coker", pos: "WR", team: "CAR", headshot_id: null };

describe("SeasonReviewSections", () => {
  it("renders colored delta cards, glyph chips, path, journey and leaders from the typed list", () => {
    const sections = buildSimReviewSections({
      decisions: [{ kind: "lineup", title: "Week 2: 49.9 points sat on your bench", detail: "d", players: [{ ...player, role: "bench" }], impact: { season_value: -0.8 } }],
      review: {
        awards: [{ key: "best_trade", kind: "trade", tone: "good", label: "Best trade", headline: "Week 3 trade", players: [{ ...player, role: "get" }], delta: { value: 12.5, unit: "pts" }, outcome: "Won the deal" }],
        rank_journey: [{ week: 1, rank: 6, wins: 0, losses: 1 }, { week: 2, rank: 3, wins: 1, losses: 1 }],
        team_count: 12,
        champion_path: { name: "Champs", seed: 1, total_rounds: 2, rounds: [{ round: 2, opponent: "Foe", pts: 100, opp_pts: 90, won: true }] },
        leaders: { league: [{ pos: "WR", rows: [{ player, pts: 200, ppg: 14, team_name: "T" }] }] },
      },
    });
    render(<SeasonReviewSections sections={sections} />);
    expect(screen.getAllByTestId("review-card")).toHaveLength(2);
    const delta = screen.getAllByText("+12.5 pts").find((el) => el.getAttribute("style")?.includes("var(--color-success)"))!; // the section summary repeats the text un-styled
    expect(delta.getAttribute("style")).toContain("var(--color-success)");
    expect(screen.getAllByText("-49.9 pts").some((el) => el.getAttribute("style")?.includes("var(--color-danger)"))).toBe(true);
    expect(screen.getByTestId("review-path")).toBeTruthy();
    expect(screen.getByTestId("review-journey")).toBeTruthy();
    expect(screen.getByTestId("review-leaders")).toBeTruthy();
    expect(screen.getByText("Won the deal")).toBeTruthy();
  });

  it("renders nothing for an empty list", () => {
    const { container } = render(<SeasonReviewSections sections={[]} />);
    expect(container.innerHTML).toBe("");
  });
});
