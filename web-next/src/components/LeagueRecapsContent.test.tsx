import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { LeagueRecapsContent } from "./LeagueRecapsContent";
import type { HistoryResponse, RecapResponse, RecapStory } from "@/lib/api";
import { api } from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      getLeagueRecap: vi.fn(),
      getLeagueHistory: vi.fn(),
    },
  };
});

function story(overrides: Partial<RecapStory>): RecapStory {
  return {
    story_type: "performance",
    title: "Highest team score",
    summary: "Posted the week's biggest total.",
    glyph: "history",
    primary_team: "Dynasty Overlords",
    secondary_team: "",
    primary_roster_id: "1",
    secondary_roster_id: "",
    players: [],
    metric_label: "Points",
    metric_value: "142.6",
    history_week: 5,
    confidence: "high",
    editorial_label: "",
    history_filter: "",
    ...overrides,
  };
}

const BASE_RECAP: RecapResponse = {
  ok: true,
  reason: "",
  max_completed_week: 5,
  recap: {
    recap_id: "recap-1",
    league_id: "league-1",
    season: "2026",
    week: 5,
    headline: "Dynasty Overlords ran away with Week 5.",
    incomplete: false,
    empty_reason: "",
    stories: [
      story({ story_type: "performance", title: "Highest team score" }),
      story({
        story_type: "matchup_close",
        title: "Nail-biter of the week",
        metric_value: "1.2",
        metric_label: "Margin",
      }),
      story({
        story_type: "trade",
        title: "Blockbuster trade",
        metric_value: "",
        history_filter: "Trades",
      }),
      story({
        story_type: "waiver",
        title: "Waiver steal",
        metric_value: "",
        history_filter: "Waivers",
      }),
    ],
  },
};

const BASE_HISTORY: HistoryResponse = {
  ok: true,
  reason: "",
  selected_league_id: "league-1",
  seasons: [{ league_id: "league-1", season: "2026", name: "Dynasty Overlords League" }],
  transactions: [
    {
      transaction_id: "tx1",
      season: "2026",
      league_id: "league-1",
      week: 5,
      timestamp: 1_700_000_000_000,
      type: "waiver",
      draft_picks: [],
      sides: [
        {
          roster_id: "1",
          team_name: "Dynasty Overlords",
          owner_handle: "@gm",
          avatar_url: "",
          receives: [
            {
              kind: "player",
              player_id: "9001",
              name: "Breakout WR",
              position: "WR",
              team: "SF",
              label: "Breakout WR",
              known: true,
            },
          ],
          drops: [],
          faab_spent: 12,
          faab_received: null,
        },
      ],
      grade: {
        kind: "waiver",
        pending: false,
        player: "Breakout WR",
        team: "Dynasty Overlords",
        letter: "B+",
        tone: "positive",
        confidence: "Medium",
        why: "$12 FAAB. Current value 3800.",
        watch: "Value and FAAB only.",
        grade_model_label: "Current pickup grade",
      },
    },
  ],
};

describe("LeagueRecapsContent", () => {
  it("colors each recap story's title by its category, not a flat/uniform color", () => {
    render(<LeagueRecapsContent leagueId="league-1" leagueName="Dynasty Overlords" initialRecap={BASE_RECAP} />);

    expect(screen.getByRole("heading", { name: "Dynasty Overlords" })).toBeInTheDocument();
    expect(screen.getByText("Week 5 recap")).toBeInTheDocument();

    const performanceTitle = screen.getByText("Highest team score");
    const matchupTitle = screen.getByText("Nail-biter of the week");
    const tradeTitle = screen.getByText("Blockbuster trade");
    const waiverTitle = screen.getByText("Waiver steal");

    expect(performanceTitle).toHaveStyle({ color: "var(--color-prestige-elite)" });
    expect(matchupTitle).toHaveStyle({ color: "var(--color-danger)" });
    expect(tradeTitle).toHaveStyle({ color: "var(--color-accent)" });
    expect(waiverTitle).toHaveStyle({ color: "var(--color-success)" });

    // None of the four should collapse onto the same flat color.
    const colors = new Set(
      [performanceTitle, matchupTitle, tradeTitle, waiverTitle].map((node) => node.style.color),
    );
    expect(colors.size).toBe(4);
  });

  it("loads History lazily and routes a story's deep link into the right filter", async () => {
    (api.getLeagueHistory as unknown as ReturnType<typeof vi.fn>).mockResolvedValue(BASE_HISTORY);

    render(<LeagueRecapsContent leagueId="league-1" leagueName="Dynasty Overlords" initialRecap={BASE_RECAP} />);

    expect(api.getLeagueHistory).not.toHaveBeenCalled();

    fireEvent.click(screen.getByText(/View waiver history/));

    await waitFor(() => expect(api.getLeagueHistory).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(screen.getAllByText("Breakout WR").length).toBeGreaterThan(0));

    // The waiver grade letter renders with its tone color (positive ->
    // --color-information), not flat text.
    expect(screen.getByText("B+")).toHaveStyle({ color: "var(--color-information)" });

    // Deep-linking from a waiver story should land on the "Waivers / Free
    // Agents" pill (modules/league_recaps.py's FILTER_WAIVERS maps there,
    // not onto its own unrendered pill) — shown pressed.
    expect(screen.getByRole("button", { name: "Waivers / Free Agents" })).toHaveAttribute("aria-pressed", "true");
  });

  it("shows the classic-page deep link on the Storylines tab instead of guessed content", () => {
    render(<LeagueRecapsContent leagueId="league-1" leagueName="Dynasty Overlords" initialRecap={BASE_RECAP} />);

    fireEvent.click(screen.getByRole("button", { name: "Storylines" }));

    expect(screen.getByText(/isn't in the new design yet/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Open classic League Memory" })).toBeInTheDocument();
  });
});
