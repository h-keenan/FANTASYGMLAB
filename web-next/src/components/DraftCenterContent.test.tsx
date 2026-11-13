import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { DraftSignalRow } from "@/lib/draftSignals";
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
    pick_tier: "Pro",
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

    expect(screen.getByRole("tab", { name: "Scouting" })).toBeInTheDocument();
    expect(screen.getByText("Pick-Rich Rebuilder")).toBeInTheDocument();
    expect(screen.getByText("#1")).toBeInTheDocument(); // Draft Capital rank tile
    expect(screen.getByText("Best Pick Buyers")).toBeInTheDocument();
    expect(screen.getByText("Pick-Rich Teams")).toBeInTheDocument();
    // Picks live on their own tab, grouped by year then round.
    fireEvent.click(screen.getByRole("tab", { name: "Picks" }));
    // My Picks is the default scope when a roster id is resolved.
    expect(screen.getByText("1st round")).toBeInTheDocument();
    expect(screen.getByText("2027 1st")).toBeInTheDocument();
    expect(screen.queryByText("2027 1st (Rival)")).not.toBeInTheDocument();
  });

  it("switches to League scope and shows every pick, with owner context", () => {
    render(
      <DraftCenterContent leagueName="Test League" data={BASE_RESPONSE} picks={PICKS} myRosterId="1" initialTab="picks" />,
    );

    fireEvent.click(screen.getByText("League"));

    expect(screen.getByText("2027 1st")).toBeInTheDocument();
    expect(screen.getByText("2027 1st (Rival)")).toBeInTheDocument();
    expect(screen.getByText(/Rival Squad/)).toBeInTheDocument();
  });

  it("hides the My Picks/League toggle when no roster id resolves, defaulting to league scope", () => {
    render(<DraftCenterContent leagueName="Test League" data={BASE_RESPONSE} picks={PICKS} myRosterId="" initialTab="picks" />);

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

  describe("structured signal rows (card schema 2)", () => {
    function signalRow(n: number, over: Partial<DraftSignalRow> = {}): DraftSignalRow {
      return {
        team_id: String(n),
        team_name: `Team ${n}`,
        avatar_url: null,
        strategy: "retool",
        strategy_display: "Retool",
        draft_rank: 10,
        draft_rank_tied: false,
        future_rank: 10,
        future_rank_tied: false,
        firsts: 0,
        reason_code: "too_few_picks",
        reason_short: "Too few picks for a retool",
        reason_long: "Draft rank #10 leaves too little flexibility for a retool build.",
        evidence: [{ key: "draft_rank", label: "Draft capital rank", value: "#10" }],
        ...over,
      };
    }
    const schema2 = (rows: DraftSignalRow[]): DraftCenterResponse => ({
      ...BASE_RESPONSE,
      decision_cards: [
        { label: "Best Pick Buyers", title: "Teams most likely to buy picks", tone: "power", schema: 2, items: rows.slice(0, 3).map((r) => `${r.team_name} | Retool | Draft #10 | Future #10 | long`), rows },
      ],
    });

    it("renders fields, not the joined string: one Picks pill, a chip, a short reason", () => {
      render(<DraftCenterContent leagueName="L" data={schema2([signalRow(1)])} picks={PICKS} myRosterId="9" />);
      expect(screen.getByText("Picks #10")).toBeInTheDocument();
      expect(screen.queryByText(/Draft #10/)).toBeNull();
      expect(screen.getByText("Retool")).toBeInTheDocument();
      expect(screen.getByText("Too few picks for a retool")).toBeInTheDocument();
      expect(document.body.textContent).not.toContain(" | ");
    });

    it("shows the top 3 and expands the rest in place with See all (n)", () => {
      render(<DraftCenterContent leagueName="L" data={schema2([1, 2, 3, 4, 5].map((n) => signalRow(n)))} picks={PICKS} myRosterId="9" />);
      expect(screen.getByText("Team 3")).toBeInTheDocument();
      expect(screen.queryByText("Team 4")).toBeNull();
      const more = screen.getByRole("button", { name: "See all (5)" });
      expect(more).toHaveAttribute("aria-expanded", "false");
      fireEvent.click(more);
      expect(screen.getByText("Team 5")).toBeInTheDocument();
    });

    it("opens a detail sheet with the full sentence and evidence on tap", () => {
      render(<DraftCenterContent leagueName="L" data={schema2([signalRow(1)])} picks={PICKS} myRosterId="9" />);
      fireEvent.click(screen.getByRole("button", { name: /Team 1, Retool, Picks #10/ }));
      const dialog = screen.getByRole("dialog", { name: "Team 1" });
      expect(dialog).toHaveTextContent("leaves too little flexibility for a retool build");
      expect(dialog).toHaveTextContent("Draft capital rank");
    });

    it("outlines the signed-in user's own team", () => {
      render(<DraftCenterContent leagueName="L" data={schema2([signalRow(1), signalRow(2)])} picks={PICKS} myRosterId="2" />);
      expect(screen.getByRole("button", { name: /Team 2,/ }).className).toContain("ui-srow-me");
      expect(screen.getByRole("button", { name: /Team 1,/ }).className).not.toContain("ui-srow-me");
    });

    it("still renders legacy strings for a response without rows", () => {
      render(<DraftCenterContent leagueName="L" data={BASE_RESPONSE} picks={PICKS} myRosterId="1" />);
      expect(screen.getByText("Team A has the leverage.")).toBeInTheDocument();
    });
  });
});
