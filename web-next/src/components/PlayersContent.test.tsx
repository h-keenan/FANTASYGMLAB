import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PlayersContent } from "./PlayersContent";
import type {
  DraftPickAsset,
  LeagueIdpValuesResponse,
  LeagueRankingsResponse,
  RankedPlayer,
  RankedPlayerStat,
} from "@/lib/api";

/** Finds the one <select> among every combobox on the page whose options
 * include `optionText` — robust against new sort/filter controls shifting
 * positional indices, unlike `getAllByRole("combobox")[n]`. */
function selectWithOption(optionText: string): HTMLElement {
  const match = screen.getAllByRole("combobox").find((select) => within(select).queryByText(optionText));
  if (!match) throw new Error(`No <select> found with an option "${optionText}"`);
  return match;
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

function player(overrides: Partial<RankedPlayer>): RankedPlayer {
  return {
    player_id: "p1",
    name: "Alpha Receiver",
    position: "WR",
    team: "SF",
    age: 22,
    status: "Active",
    injury_status: null,
    tier: "starter",
    score: 1500,
    overall_rank: 1,
    position_rank: 1,
    rank_unavailable_reason: null,
    opportunity_label: null,
    overall_rating: 90,
    ...overrides,
  };
}

const DATA: LeagueRankingsResponse = {
  ok: true,
  players: [
    player({ player_id: "a", name: "Alpha Receiver", position: "WR", age: 22, injury_status: null }),
    player({ player_id: "b", name: "Beta Back", position: "RB", age: 30, injury_status: "Questionable", score: 1200 }),
    player({ player_id: "c", name: "Gamma Kicker", position: "K", age: 26, status: "Inactive", score: 800 }),
  ],
};

describe("PlayersContent", () => {
  it("renders every player in the pool by default", () => {
    render(<PlayersContent leagueId="league1" leagueName="Dynasty Overlords" data={DATA} />);

    expect(screen.getByRole("heading", { name: "Dynasty Overlords" })).toBeInTheDocument();
    expect(screen.getByText("Alpha Receiver")).toBeInTheDocument();
    expect(screen.getByText("Beta Back")).toBeInTheDocument();
    expect(screen.getByText("Gamma Kicker")).toBeInTheDocument();
    expect(screen.getByText("3 matching players.")).toBeInTheDocument();
  });

  it("filters by search text", () => {
    render(<PlayersContent leagueId="league1" leagueName="Dynasty Overlords" data={DATA} />);

    fireEvent.change(screen.getByPlaceholderText("Search players"), { target: { value: "beta" } });

    expect(screen.getByText("Beta Back")).toBeInTheDocument();
    expect(screen.queryByText("Alpha Receiver")).not.toBeInTheDocument();
    expect(screen.getByText("1 matching player.")).toBeInTheDocument();
  });

  it("filters by position", () => {
    render(<PlayersContent leagueId="league1" leagueName="Dynasty Overlords" data={DATA} />);

    const [positionSelect] = screen.getAllByRole("combobox");
    fireEvent.change(positionSelect, { target: { value: "K" } });

    expect(screen.getByText("Gamma Kicker")).toBeInTheDocument();
    expect(screen.queryByText("Alpha Receiver")).not.toBeInTheDocument();
  });

  it("links each row's Compare CTA into Player Compare with the right player id", () => {
    render(<PlayersContent leagueId="league1" leagueName="Dynasty Overlords" data={DATA} />);

    const links = screen.getAllByRole("link", { name: "Compare" });
    expect(links[0]).toHaveAttribute("href", "/player-compare/league1?a=a&name=Dynasty%20Overlords");
  });

  it("shows the empty-filter message when nothing matches", () => {
    render(<PlayersContent leagueId="league1" leagueName="Dynasty Overlords" data={DATA} />);

    fireEvent.change(screen.getByPlaceholderText("Search players"), { target: { value: "nonexistent" } });

    expect(screen.getByText("No players match")).toBeInTheDocument();
  });

  it("hides the Players/Picks toggle and roster-status facet when no picks or rosters are given", () => {
    render(<PlayersContent leagueId="league1" leagueName="Dynasty Overlords" data={DATA} />);

    expect(screen.queryByText("Picks")).not.toBeInTheDocument();
    expect(screen.queryByText("Any roster status")).not.toBeInTheDocument();
  });

  describe("Picks view", () => {
    const PICKS: DraftPickAsset[] = [
      pick({ pick_id: "2027:1:1", owner_team_name: "Dynasty Overlords" }),
      pick({ pick_id: "2028:1:1", season: 2028, owner_roster_id: "2", owner_team_name: "Rival Squad", label: "2028 1st" }),
    ];

    it("shows the Players/Picks toggle once picks are given, defaulting to Players", () => {
      render(<PlayersContent leagueId="league1" leagueName="Dynasty Overlords" data={DATA} picks={PICKS} />);

      expect(screen.getByText("Alpha Receiver")).toBeInTheDocument();
      expect(screen.queryByText("2027 1st")).not.toBeInTheDocument();
    });

    it("switches to Picks and shows every pick, grouped by season with owner context", () => {
      render(<PlayersContent leagueId="league1" leagueName="Dynasty Overlords" data={DATA} picks={PICKS} />);

      fireEvent.click(screen.getByText("Picks"));

      expect(screen.queryByText("Alpha Receiver")).not.toBeInTheDocument();
      expect(screen.getByText("2027 1st")).toBeInTheDocument();
      expect(screen.getByText("2028 1st")).toBeInTheDocument();
      expect(screen.getByText(/Rival Squad/)).toBeInTheDocument();
    });
  });

  describe("roster-status facet", () => {
    const ROSTERS = [
      { roster_id: 1, players: ["a"] },
      { roster_id: 2, players: ["b"] },
    ];

    it("stays hidden without roster data even when picks are present", () => {
      render(
        <PlayersContent
          leagueId="league1"
          leagueName="Dynasty Overlords"
          data={DATA}
          picks={[pick({})]}
        />,
      );

      expect(screen.queryByText("Any roster status")).not.toBeInTheDocument();
    });

    it("filters to rostered players using the union of every roster's players array", () => {
      render(<PlayersContent leagueId="league1" leagueName="Dynasty Overlords" data={DATA} rosters={ROSTERS} />);

      fireEvent.change(selectWithOption("Rostered"), { target: { value: "Rostered" } });

      expect(screen.getByText("Alpha Receiver")).toBeInTheDocument();
      expect(screen.getByText("Beta Back")).toBeInTheDocument();
      expect(screen.queryByText("Gamma Kicker")).not.toBeInTheDocument();
    });

    it("filters to available (unrostered) players", () => {
      render(<PlayersContent leagueId="league1" leagueName="Dynasty Overlords" data={DATA} rosters={ROSTERS} />);

      fireEvent.change(selectWithOption("Rostered"), { target: { value: "Available" } });

      expect(screen.queryByText("Alpha Receiver")).not.toBeInTheDocument();
      expect(screen.queryByText("Beta Back")).not.toBeInTheDocument();
      expect(screen.getByText("Gamma Kicker")).toBeInTheDocument();
    });
  });

  describe("Madden-style stat sort", () => {
    function statsPlayer(overrides: Partial<RankedPlayer>, stats: RankedPlayerStat[]): RankedPlayer {
      return player({ ...overrides, stats });
    }

    const WITH_STATS: LeagueRankingsResponse = {
      ok: true,
      players: [
        statsPlayer(
          { player_id: "a", name: "Alpha Receiver", position: "WR", score: 900, overall_rating: 70 },
          [
            { key: "targets", label: "Targets", value: 60, format: "count", percentile: 40 },
            { key: "rec_yards", label: "Rec Yards", value: 600, format: "yards", percentile: 35 },
          ],
        ),
        statsPlayer(
          { player_id: "b", name: "Beta Receiver", position: "WR", score: 700, overall_rating: 95 },
          [
            { key: "targets", label: "Targets", value: 150, format: "count", percentile: 99 },
            { key: "rec_yards", label: "Rec Yards", value: 1400, format: "yards", percentile: 97 },
          ],
        ),
      ],
    };

    it("defaults to sorting by Value (the server's existing order) and hides the Raw/Percentile toggle", () => {
      render(<PlayersContent leagueId="league1" leagueName="Dynasty Overlords" data={WITH_STATS} />);

      const rows = screen.getAllByText(/Receiver$/).map((el) => el.textContent);
      expect(rows).toEqual(["Alpha Receiver", "Beta Receiver"]);
      expect(screen.queryByText("Raw")).not.toBeInTheDocument();
      expect(screen.queryByText("Percentile")).not.toBeInTheDocument();
    });

    it("offers every stat the visible pool carries, and re-sorts the board by raw value when picked", () => {
      render(<PlayersContent leagueId="league1" leagueName="Dynasty Overlords" data={WITH_STATS} />);

      const sortSelect = selectWithOption("Rec Yards");
      fireEvent.change(sortSelect, { target: { value: "rec_yards" } });

      // Beta has the higher Rec Yards total (1400 vs 600) despite a lower
      // Value score — the stat sort, not the server's default order, wins.
      const rows = screen.getAllByText(/Receiver$/).map((el) => el.textContent);
      expect(rows).toEqual(["Beta Receiver", "Alpha Receiver"]);
      expect(screen.getByText("600")).toBeInTheDocument();
      expect(screen.getByText("1400")).toBeInTheDocument();
    });

    it("switches to percentile mode and re-sorts/re-displays by the stat's position-group percentile", () => {
      render(<PlayersContent leagueId="league1" leagueName="Dynasty Overlords" data={WITH_STATS} />);

      fireEvent.change(selectWithOption("Rec Yards"), { target: { value: "rec_yards" } });
      fireEvent.click(screen.getByText("Percentile"));

      expect(screen.getByText("97th")).toBeInTheDocument();
      expect(screen.getByText("35th")).toBeInTheDocument();
    });
  });

  describe("Add to Trade quick-add", () => {
    it("deep-links each row into Trade Analyzer with ?playerId=, same convention as Waivers/Trade Hub", () => {
      render(<PlayersContent leagueId="league1" leagueName="Dynasty Overlords" data={DATA} />);

      const links = screen.getAllByRole("link", { name: "Add to Trade" });
      expect(links[0]).toHaveAttribute(
        "href",
        "/trade-analyzer/league1?name=Dynasty+Overlords&playerId=a",
      );
    });
  });

  describe("IDP leagues", () => {
    const IDP: LeagueIdpValuesResponse = {
      ok: true,
      idp: true,
      below_replacement_ids: [],
      unscored_keys: ["bonus_def_int_td_50p"],
      players: [
        {
          player_id: "d1",
          name: "Edge Rusher",
          position: "DE",
          family: "DL",
          team: "DET",
          age: 26,
          injury_status: null,
          value: 2706,
          ppg: 15.5,
          projected_points: 240,
          points_over_replacement: 53,
          confidence: "high",
          idp_rank: 1,
        },
        {
          player_id: "d2",
          name: "Thumper Backer",
          position: "LB",
          family: "LB",
          team: "CLE",
          age: 23,
          injury_status: null,
          value: 2358,
          ppg: 16.7,
          projected_points: 220,
          points_over_replacement: 40,
          confidence: "low",
          idp_rank: 2,
        },
      ],
    };

    it("leaves a non-IDP league exactly as it was: no defense chips", () => {
      render(
        <PlayersContent
          leagueId="league1"
          leagueName="Dynasty Overlords"
          data={DATA}
          idp={{ ok: true, idp: false, players: [] }}
        />,
      );
      const [positionSelect] = screen.getAllByRole("combobox");
      expect(within(positionSelect).queryByText("DL")).not.toBeInTheDocument();
      expect(screen.queryByText("Edge Rusher")).not.toBeInTheDocument();
    });

    it("keeps defenders off the offensive board and shows them, valued and caveated, under a DL/LB/DB chip", () => {
      render(<PlayersContent leagueId="league1" leagueName="Dynasty Overlords" data={DATA} idp={IDP} />);
      expect(screen.queryByText("Edge Rusher")).not.toBeInTheDocument();

      const [positionSelect] = screen.getAllByRole("combobox");
      fireEvent.change(positionSelect, { target: { value: "DL" } });

      expect(screen.getByText("Edge Rusher")).toBeInTheDocument();
      expect(screen.queryByText("Thumper Backer")).not.toBeInTheDocument();
      expect(screen.queryByText("Alpha Receiver")).not.toBeInTheDocument();
      expect(screen.getByText("Solid sample")).toBeInTheDocument();
      expect(screen.getByText(/not market prices/)).toBeInTheDocument();
      expect(screen.getByText(/bonus_def_int_td_50p/)).toBeInTheDocument();
      // Compare / Add to Trade are not offered for defenders (those engines do not value them yet).
      expect(screen.queryByRole("link", { name: "Compare" })).not.toBeInTheDocument();
      expect(screen.queryByRole("link", { name: "Add to Trade" })).not.toBeInTheDocument();
    });
  });
});
