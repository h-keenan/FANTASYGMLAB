import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DraftCenterContent } from "./DraftCenterContent";
import type { DraftCenterResponse, DraftPickAsset, DraftPosture } from "@/lib/api";

function posture(overrides: Partial<DraftPosture>): DraftPosture {
  return {
    label: "Pick-Rich Rebuilder",
    note: "Rebuild path already has strong pick insulation.",
    tone: "opportunity",
    draft_capital_rank: 1,
    draft_capital_rank_tied: false,
    draft_capital: 42,
    future_draft_capital_rank: 2,
    future_draft_capital_rank_tied: false,
    future_draft_capital: 30,
    strategy_display: "Rebuild",
    power_rank: 8,
    power_rank_tied: false,
    franchise_rank: 3,
    franchise_rank_tied: false,
    first_rounders: 3,
    pick_count: 7,
    ...overrides,
  };
}

function pick(overrides: Partial<DraftPickAsset>): DraftPickAsset {
  return {
    pick_id: "2027:1:1",
    label: "2027 1st",
    score: 4200,
    season: 2027,
    round: 1,
    original_roster_id: "1",
    owner_roster_id: "1",
    original_team_name: "Dynasty Overlords",
    owner_team_name: "Dynasty Overlords",
    pick_tier: "Premium",
    projected_pick_range: "Picks 1-4",
    projection_confidence: 0.72,
    ...overrides,
  };
}

const BASE_RESPONSE: DraftCenterResponse = {
  ok: true,
  reason: "",
  posture: posture({}),
  posture_reason: "",
  decision_cards: [
    { label: "Best Pick Buyers", title: "Teams most likely to buy picks", tone: "power", items: ["Team A has the leverage."] },
  ],
  partner_cards: [
    { label: "Pick-Rich Teams", title: "Teams with surplus capital", tone: "franchise", items: ["Team B can move a first."] },
  ],
};

const PICKS: DraftPickAsset[] = [
  pick({ pick_id: "2027:1:1", owner_roster_id: "1", owner_team_name: "Dynasty Overlords" }),
  pick({ pick_id: "2027:1:2", owner_roster_id: "2", owner_team_name: "Rival Squad", original_roster_id: "2", label: "2027 1st (Rival)" }),
];

describe("DraftCenterContent", () => {
  it("renders posture tiles, pick values, and both card sections", () => {
    render(
      <DraftCenterContent leagueName="Test League" data={BASE_RESPONSE} picks={PICKS} myRosterId="1" />,
    );

    expect(screen.getByText("Pick-Rich Rebuilder")).toBeInTheDocument();
    expect(screen.getByText("#1")).toBeInTheDocument(); // Draft Capital rank tile
    expect(screen.getByText("Best Pick Buyers")).toBeInTheDocument();
    expect(screen.getByText("Pick-Rich Teams")).toBeInTheDocument();
    // My Picks is the default scope when a roster id is resolved.
    expect(screen.getByText("2027 1st")).toBeInTheDocument();
    expect(screen.queryByText("2027 1st (Rival)")).not.toBeInTheDocument();
  });

  it("switches to League scope and shows every pick, with owner context", () => {
    render(
      <DraftCenterContent leagueName="Test League" data={BASE_RESPONSE} picks={PICKS} myRosterId="1" />,
    );

    fireEvent.click(screen.getByText("League"));

    expect(screen.getByText("2027 1st")).toBeInTheDocument();
    expect(screen.getByText("2027 1st (Rival)")).toBeInTheDocument();
    expect(screen.getByText(/Rival Squad/)).toBeInTheDocument();
  });

  it("hides the My Picks/League toggle when no roster id resolves, defaulting to league scope", () => {
    render(<DraftCenterContent leagueName="Test League" data={BASE_RESPONSE} picks={PICKS} myRosterId="" />);

    expect(screen.queryByText("My Picks")).not.toBeInTheDocument();
    expect(screen.getByText("2027 1st (Rival)")).toBeInTheDocument();
  });

  it("shows the posture_reason message when posture is null", () => {
    render(
      <DraftCenterContent
        leagueName="Test League"
        data={{ ...BASE_RESPONSE, posture: null, posture_reason: "not_a_member_of_league" }}
        picks={[]}
        myRosterId=""
      />,
    );

    expect(screen.getByText(/don't appear to have a roster/)).toBeInTheDocument();
  });
});
