import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { LiveDraftContent } from "./LiveDraftContent";
import type {
  LiveDraftDiscoveryResponse,
  LiveDraftRecommendation,
  LiveDraftStateResponse,
} from "@/lib/api";

function recommendation(overrides: Partial<LiveDraftRecommendation>): LiveDraftRecommendation {
  return {
    player_id: "p1",
    name: "Star Wideout",
    position: "WR",
    team: "KC",
    age: 24,
    tier: "Elite",
    league_adjusted_draft_score: 105.4,
    overall_rating: 92,
    recommendation_role: "Recommended pick",
    recommendation_reason: "Highest remaining league-adjusted score.",
    position_need_impact: "Fills WR need",
    immediate_roster_impact: "Improves a thin WR room immediately.",
    confidence: "High",
    adp_delta: 1.5,
    ...overrides,
  };
}

const DISCOVERY_NO_DRAFTS: LiveDraftDiscoveryResponse = {
  ok: true,
  error: "",
  drafts: [],
  active_draft_id: "",
  is_premium: true,
  upsell: null,
};

const DISCOVERY_ONE_LIVE: LiveDraftDiscoveryResponse = {
  ok: true,
  error: "",
  drafts: [{ draft_id: "draft-1", season: "2026", status: "drafting", rounds: 15, name: "Startup Draft" }],
  active_draft_id: "draft-1",
  is_premium: true,
  upsell: null,
};

const DISCOVERY_TWO_LIVE: LiveDraftDiscoveryResponse = {
  ok: true,
  error: "",
  drafts: [
    { draft_id: "draft-1", season: "2026", status: "drafting", rounds: 15, name: "Startup Draft" },
    { draft_id: "draft-2", season: "2026", status: "paused", rounds: 4, name: "Rookie Draft" },
  ],
  active_draft_id: "draft-1",
  is_premium: true,
  upsell: null,
};

const STATE: LiveDraftStateResponse = {
  ok: true,
  reason: "",
  is_premium: true,
  upsell: null,
  pick_data_stale: false,
  status: "drafting",
  rounds: 15,
  teams: 12,
  picks_made: 3,
  current_pick: 4,
  current_round: 1,
  current_team_name: "My Dynasty",
  current_manager_name: "GM One",
  my_slot: 4,
  is_my_pick: true,
  picks_until_mine: 0,
  my_upcoming_picks: [4, 21],
  positional_run: "WR 2 | RB 1",
  last_updated: "2026-10-15 18:00:00 UTC",
  score_label: "Dynasty Score",
  league_settings: { qb_format: "1QB", scoring_format: "PPR", league_format: "Dynasty" },
  recommendations: [recommendation({}), recommendation({ player_id: "p2", name: "Backup Runner", recommendation_role: "Alternative" })],
  pick_rows: [
    {
      pick_no: 1,
      round: 1,
      round_pick: "1.01",
      player_id: "p9",
      player_name: "Already Drafted",
      position: "RB",
      team: "NYJ",
      fantasy_team: "Rival Squad",
      is_mine: false,
    },
  ],
  rankings: [
    {
      player_id: "p1",
      name: "Star Wideout",
      position: "WR",
      team: "KC",
      age: 24,
      tier: "Elite",
      is_rookie: false,
      overall_rank: 1,
      position_rank: 1,
      canonical_overall_rank: 1,
      canonical_position_rank: 1,
      rank_scoring_format: "",
      rank_unavailable_reason: "",
      base_value: 100,
      league_adjusted_draft_score: 105.4,
      overall_rating: 92,
      movement: 3,
      recommendation_label: "Best Available",
      recommendation_reason: "",
    },
  ],
  team_rankings: [
    {
      roster_id: 4,
      team_name: "My Dynasty",
      is_mine: true,
      team_rank: 1,
      movement: 0,
      trend_label: "Best Team",
      live_team_score: 94,
      roster_count: 9,
      pick_count: 3,
      positions: "WR 2 · RB 1",
      top_player: "Star Wideout",
      starter_value: 700,
      total_value: 900,
    },
  ],
};

describe("LiveDraftContent", () => {
  it("shows the Premium upsell instead of the empty-drafts message for a Free caller", () => {
    render(
      <LiveDraftContent
        leagueId="league-1"
        leagueName="Dynasty Overlords"
        discovery={{ ...DISCOVERY_NO_DRAFTS, is_premium: false, upsell: null }}
        selectedDraftId=""
        onSelectDraft={vi.fn()}
        state={null}
        stateError={null}
        onRefresh={vi.fn()}
      />,
    );

    expect(screen.getByRole("heading", { name: "Draft with real-time recommendations" })).toBeInTheDocument();
    expect(screen.queryByText("No Sleeper drafts were found for this league yet.")).not.toBeInTheDocument();
  });

  it("shows the Premium upsell even when a live draft actually exists for a Free caller", () => {
    render(
      <LiveDraftContent
        leagueId="league-1"
        leagueName="Dynasty Overlords"
        discovery={{ ...DISCOVERY_ONE_LIVE, is_premium: false, upsell: { title: "Custom title", body: "Custom body" } }}
        selectedDraftId="draft-1"
        onSelectDraft={vi.fn()}
        state={null}
        stateError={null}
        onRefresh={vi.fn()}
      />,
    );

    expect(screen.getByRole("heading", { name: "Custom title" })).toBeInTheDocument();
    expect(screen.getByText("Custom body")).toBeInTheDocument();
  });

  it("shows the empty state when the league has no Sleeper drafts", () => {
    render(
      <LiveDraftContent
        leagueId="league-1"
        leagueName="Dynasty Overlords"
        discovery={DISCOVERY_NO_DRAFTS}
        selectedDraftId=""
        onSelectDraft={vi.fn()}
        state={null}
        stateError={null}
        onRefresh={vi.fn()}
      />,
    );

    expect(screen.getByText("No Sleeper drafts were found for this league yet.")).toBeInTheDocument();
  });

  it("shows a loading message while the first snapshot is still in flight", () => {
    render(
      <LiveDraftContent
        leagueId="league-1"
        leagueName="Dynasty Overlords"
        discovery={DISCOVERY_ONE_LIVE}
        selectedDraftId="draft-1"
        onSelectDraft={vi.fn()}
        state={null}
        stateError={null}
        onRefresh={vi.fn()}
      />,
    );

    expect(screen.getByText("Loading the live draft board…")).toBeInTheDocument();
  });

  it("renders on-the-clock status, the primary recommendation, rankings, team board, and pick board", () => {
    render(
      <LiveDraftContent
        leagueId="league-1"
        leagueName="Dynasty Overlords"
        discovery={DISCOVERY_ONE_LIVE}
        selectedDraftId="draft-1"
        onSelectDraft={vi.fn()}
        state={STATE}
        stateError={null}
        onRefresh={vi.fn()}
      />,
    );

    expect(screen.getByText("Pick 4 · Round 1")).toBeInTheDocument();
    expect(screen.getByText("On the clock")).toBeInTheDocument();
    expect(screen.getAllByText("Star Wideout").length).toBeGreaterThan(0);
    expect(screen.getByText("Backup Runner")).toBeInTheDocument();
    expect(screen.getByText("Also consider")).toBeInTheDocument();
    expect(screen.getByText("▲ 3")).toBeInTheDocument();
    expect(screen.getByText("My Dynasty (You)")).toBeInTheDocument();
    expect(screen.getByText("Already Drafted")).toBeInTheDocument();
  });

  it("offers a draft selector only when more than one live/paused draft exists", () => {
    const { rerender } = render(
      <LiveDraftContent
        leagueId="league-1"
        leagueName="Dynasty Overlords"
        discovery={DISCOVERY_ONE_LIVE}
        selectedDraftId="draft-1"
        onSelectDraft={vi.fn()}
        state={STATE}
        stateError={null}
        onRefresh={vi.fn()}
      />,
    );
    expect(screen.queryByRole("combobox", { name: "" })).toBeInTheDocument(); // the rankings filter select only

    const onSelectDraft = vi.fn();
    rerender(
      <LiveDraftContent
        leagueId="league-1"
        leagueName="Dynasty Overlords"
        discovery={DISCOVERY_TWO_LIVE}
        selectedDraftId="draft-1"
        onSelectDraft={onSelectDraft}
        state={STATE}
        stateError={null}
        onRefresh={vi.fn()}
      />,
    );
    const selects = screen.getAllByRole("combobox");
    expect(selects.length).toBe(2);
    fireEvent.change(selects[0], { target: { value: "draft-2" } });
    expect(onSelectDraft).toHaveBeenCalledWith("draft-2");
  });

  it("calls onRefresh when Refresh Draft is clicked", () => {
    const onRefresh = vi.fn();
    render(
      <LiveDraftContent
        leagueId="league-1"
        leagueName="Dynasty Overlords"
        discovery={DISCOVERY_ONE_LIVE}
        selectedDraftId="draft-1"
        onSelectDraft={vi.fn()}
        state={STATE}
        stateError={null}
        onRefresh={onRefresh}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Refresh Draft" }));
    expect(onRefresh).toHaveBeenCalled();
  });

  it("shows the draft-complete banner and stops implying active polling copy", () => {
    render(
      <LiveDraftContent
        leagueId="league-1"
        leagueName="Dynasty Overlords"
        discovery={DISCOVERY_ONE_LIVE}
        selectedDraftId="draft-1"
        onSelectDraft={vi.fn()}
        state={{ ...STATE, status: "complete" }}
        stateError={null}
        onRefresh={vi.fn()}
      />,
    );
    expect(screen.getByText("Draft complete. Live polling is paused.")).toBeInTheDocument();
  });
});
