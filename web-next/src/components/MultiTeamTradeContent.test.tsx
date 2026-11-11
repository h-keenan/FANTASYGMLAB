import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { api, type DraftPickAsset, type RankedPlayer, type TeamProfile } from "@/lib/api";
import type { MultiTeamTradeResponse } from "@/lib/multiTeamTrade";

import { MultiTeamTradeContent, TradeModeToggle, failureMessage } from "./MultiTeamTradeContent";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, api: { ...actual.api, postMultiTeamTradeAnalyzer: vi.fn() } };
});
vi.mock("@/lib/shareCard/clientRender", () => ({ renderMultiTradeCardBlob: vi.fn() }));
vi.mock("@/lib/leaguePlayerSearch", async () => {
  const actual = await vi.importActual<typeof import("@/lib/leaguePlayerSearch")>("@/lib/leaguePlayerSearch");
  return { ...actual, useLeaguePlayerSearch: () => [] };
});

const post = api.postMultiTeamTradeAnalyzer as unknown as ReturnType<typeof vi.fn>;

function player(id: string, name: string, position: string): RankedPlayer {
  return {
    player_id: id,
    name,
    position,
    team: "SF",
    age: 24,
    status: "Active",
    injury_status: null,
    tier: "starter",
    score: 1500,
    overall_rank: 12,
    position_rank: 4,
    rank_unavailable_reason: null,
    opportunity_label: null,
    overall_rating: 72,
  } as RankedPlayer;
}

const RANKINGS = [player("a", "Alpha Back", "RB"), player("b", "Bravo Wideout", "WR"), player("c", "Charlie Tight", "TE")];
const ROSTERS = [
  { roster_id: "1", players: ["a"] },
  { roster_id: "2", players: ["b"] },
  { roster_id: "3", players: ["c"] },
];
const PROFILES = Object.fromEntries(
  ["1", "2", "3"].map((id) => [id, { team_name: `Team ${id}`, owner_name: `Owner ${id}`, roster_id: id }]),
) as unknown as Record<string, TeamProfile>;

function renderBuilder() {
  return render(
    <MultiTeamTradeContent
      leagueId="league-1"
      leagueName="Dynasty Overlords"
      myRosterId="1"
      rankings={RANKINGS}
      picks={[] as DraftPickAsset[]}
      rosters={ROSTERS}
      teamProfiles={PROFILES}
      lens="Dynasty"
      modeToggle={<TradeModeToggle mode="multi" onChange={() => {}} />}
    />,
  );
}

function addTeam(name: string) {
  fireEvent.change(screen.getByLabelText("Add a team"), { target: { value: name } });
  fireEvent.click(screen.getByRole("button", { name: "Add team" }));
}

function addAsset(teamName: string, assetName: string, destination: string) {
  const panel = screen.getAllByTestId("team-panel").find((p) => within(p).queryByText(teamName));
  fireEvent.click(within(panel!).getByRole("button", { name: "Add asset" }));
  fireEvent.click(screen.getByText(assetName));
  fireEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: destination }));
}

function team(id: string, name: string, over: Record<string, unknown> = {}) {
  return {
    roster_id: id,
    team_name: name,
    is_perspective: id === "1",
    sends: [],
    receives: [],
    verdict: { ui_verdict: "FAIR" },
    trade_score: id === "3" ? -900 : 400,
    market_delta: id === "3" ? -700 : 350,
    lineup_delta: { per_week: 2 },
    tone: id === "3" ? "decline" : "accept",
    outcome: id === "3" ? "loses" : "wins",
    why: [{ factor: "market", text: `${name} market reason` }],
    veto_risk: null,
    ...over,
  };
}

const OK: MultiTeamTradeResponse = {
  status: "ok",
  teams: [team("1", "Team 1"), team("2", "Team 2"), team("3", "Team 3")] as never,
  summary: {
    headline: "Team 3 is the team most hurt by this deal.",
    team_count: 3,
    balance: { id: "lopsided", label: "Lopsided: at least one team is giving up a lot", spread: 1300, best_roster_id: "1", worst_roster_id: "3" },
    most_hurt_roster_id: "3",
    best_off_roster_id: "1",
    ranking: [],
  },
  veto_locked: true,
  veto_upsell: { title: "Spot a vetoable trade", body: "Veto risk is Pro." },
};

function buildThreeTeamTrade() {
  addTeam("2");
  addTeam("3");
  addAsset("Team 1", "Alpha Back", "Team 2");
  addAsset("Team 2", "Bravo Wideout", "Team 3");
  addAsset("Team 3", "Charlie Tight", "Team 1");
}

describe("MultiTeamTradeContent", () => {
  beforeEach(() => post.mockReset());

  it("needs 3 teams before Analyze is ready and says why", () => {
    renderBuilder();
    expect(screen.getByRole("button", { name: /Analyze 1-team trade/ })).toBeDisabled();
    expect(screen.getByText(/Add at least 2 more teams/)).toBeInTheDocument();
  });

  it("routes each asset to a destination team and sends transfers for the perspective team", async () => {
    post.mockResolvedValue(OK);
    renderBuilder();
    buildThreeTeamTrade();
    const analyze = screen.getByRole("button", { name: /Analyze 3-team trade/ });
    expect(analyze).toBeEnabled();
    fireEvent.click(analyze);
    await waitFor(() => expect(post).toHaveBeenCalled());
    expect(post.mock.calls[0][1]).toEqual({
      transfers: [
        { type: "player", id: "a", from_roster_id: "1", to_roster_id: "2" },
        { type: "player", id: "b", from_roster_id: "2", to_roster_id: "3" },
        { type: "player", id: "c", from_roster_id: "3", to_roster_id: "1" },
      ],
      perspectiveRosterId: "1",
      lens: "Dynasty",
    });
  });

  it("shows the most hurt banner, a card per team, and the locked veto upsell", async () => {
    post.mockResolvedValue(OK);
    renderBuilder();
    buildThreeTeamTrade();
    fireEvent.click(screen.getByRole("button", { name: /Analyze 3-team trade/ }));
    expect(await screen.findByTestId("most-hurt-banner")).toHaveTextContent("Most hurt: Team 3");
    expect(screen.getAllByTestId("team-result")).toHaveLength(3);
    expect(screen.getByText("Spot a vetoable trade")).toBeInTheDocument();
    expect(screen.getByTestId("multi-team-share")).toHaveTextContent("Pitch it to the other managers");
  });

  it("turns API errors into plain language", async () => {
    post.mockResolvedValue({ status: "invalid", errors: [{ code: "asset_not_owned", message: "Alpha Back is not on Team 1" }] });
    renderBuilder();
    buildThreeTeamTrade();
    fireEvent.click(screen.getByRole("button", { name: /Analyze 3-team trade/ }));
    expect(await screen.findByTestId("multi-team-failure")).toHaveTextContent(/no longer on the team you sent it from/);
  });

  it("explains rate limits and a busy server in plain language", () => {
    expect(failureMessage({ status: 429, retryAfterSeconds: 20 })).toMatch(/Try again in 20 seconds/);
    expect(failureMessage({ status: 429 })).toMatch(/Try again in a minute/);
    expect(failureMessage({ status: 503, code: "server_busy" })).toMatch(/busy right now/);
    expect(failureMessage(new Error("Could not reach the server."))).toBe("Could not reach the server.");
  });

  it("shows the unavailable reason with the shared failure card", async () => {
    post.mockResolvedValue({ status: "unavailable", reason: "unsupported_platform" });
    renderBuilder();
    buildThreeTeamTrade();
    fireEvent.click(screen.getByRole("button", { name: /Analyze 3-team trade/ }));
    expect(await screen.findByTestId("multi-team-failure")).toHaveTextContent(/available for Sleeper leagues/);
  });

  it("opens a 3-team idea prefilled and grades it once, without a tap on Analyze", async () => {
    post.mockResolvedValue(OK);
    const transfers = [
      { type: "player" as const, id: "a", from_roster_id: "1", to_roster_id: "2" },
      { type: "player" as const, id: "b", from_roster_id: "2", to_roster_id: "3" },
      { type: "player" as const, id: "c", from_roster_id: "3", to_roster_id: "1" },
    ];
    render(
      <MultiTeamTradeContent
        leagueId="league-1"
        leagueName="Dynasty Overlords"
        myRosterId="1"
        rankings={RANKINGS}
        picks={[] as DraftPickAsset[]}
        rosters={ROSTERS}
        teamProfiles={PROFILES}
        lens="Dynasty"
        modeToggle={<TradeModeToggle mode="multi" onChange={() => {}} />}
        prefill={transfers}
      />,
    );
    expect(screen.getAllByTestId("team-panel")).toHaveLength(3);
    await waitFor(() => expect(post).toHaveBeenCalledTimes(1));
    expect(post.mock.calls[0][1]).toEqual({ transfers, perspectiveRosterId: "1", lens: "Dynasty" });
    expect(await screen.findByTestId("most-hurt-banner")).toBeInTheDocument();
  });

  it("removing a team drops the assets routed to it", () => {
    renderBuilder();
    buildThreeTeamTrade();
    fireEvent.click(screen.getByRole("button", { name: "Remove Team 3" }));
    expect(screen.queryByText("Charlie Tight")).not.toBeInTheDocument();
    expect(screen.queryByText("Bravo Wideout")).not.toBeInTheDocument();
  });
});
