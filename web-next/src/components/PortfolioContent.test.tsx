import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PortfolioContent, PortfolioShell } from "./PortfolioContent";
import { PORTFOLIO_CARD_MIN_HEIGHT, PORTFOLIO_SHELL_SKELETON_COUNT } from "@/lib/portfolioLoader";
import { api, type BriefingItem, type PortfolioLeague, type PortfolioResponse } from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      removeSavedLeague: vi.fn(),
    },
  };
});

function briefingItem(overrides: Partial<BriefingItem>): BriefingItem {
  return {
    category: "top_priority",
    headline: "Trade away Test Player before Week 10",
    reason: "Value is trending down after a usage drop.",
    supporting_context: null,
    destination: "trade_hub",
    route_player_id: "4046",
    route_player_name: "Test Player",
    route_player_position: "RB",
    route_player_team: "SF",
    route_player_tier: "starter",
    route_player_score: 88,
    route_player_injury_status: "",
    mentioned_players: [],
    recommendation_narrative: null,
    presentation: null,
    recommendation_id: "rec-1",
    tier_label: "Starter",
    ...overrides,
  };
}

function league(overrides: Partial<PortfolioLeague>): PortfolioLeague {
  return {
    league_id: "league-1",
    league_name: "Dynasty Overlords",
    team_name: "The Contenders",
    team_avatar_url: "",
    wins: 7,
    losses: 3,
    ties: 0,
    health_flag: "Stable",
    power_rank: 1,
    power_rank_tied: false,
    franchise_rank: 2,
    franchise_rank_tied: false,
    roster_value_rank: 1,
    roster_value_rank_tied: false,
    archetype: "contender",
    archetype_label: "Contender",
    top_asset: null,
    top_item: briefingItem({}),
    top_items: [
      briefingItem({}),
      briefingItem({
        category: "watch",
        headline: "Test Backup is questionable for Sunday",
        reason: "Listed questionable with a hamstring issue.",
        recommendation_id: "rec-2",
      }),
    ],
    ...overrides,
  };
}

const BASE_RESPONSE: PortfolioResponse = {
  ok: true,
  is_premium: true,
  lens: "Dynasty",
  leagues: [league({})],
  failed_leagues: [],
  upsell: null,
};

describe("PortfolioContent", () => {
  beforeEach(() => {
    vi.mocked(api.removeSavedLeague).mockReset();
  });

  it("renders a league card with its record, rank, and every quick-glance signal", () => {
    render(<PortfolioContent data={BASE_RESPONSE} />);

    expect(screen.getByText(/The Contenders — Dynasty Overlords/)).toBeInTheDocument();
    // Top-3 shows the rank in the gold/silver/bronze pill badge, not
    // repeated in the record metadata line (mirrors modules/portfolio_page.py).
    expect(screen.getByText("7-3")).toBeInTheDocument();
    expect(screen.getByText("#1")).toBeInTheDocument();
    expect(screen.getByText("Value is trending down after a usage drop.")).toBeInTheDocument();
    expect(screen.getByText("Listed questionable with a hamstring issue.")).toBeInTheDocument();
    expect(screen.getByText("Top Priority")).toBeInTheDocument();
    expect(screen.getByText("Watch")).toBeInTheDocument();
    expect(screen.getByText("Open Dynasty Overlords Dashboard →")).toBeInTheDocument();
  });

  // coridian_, 2026-10-19 (screenshot): "this is a trade and a usage
  // alert and something else, but they're not clearly segregated, and so
  // it all looks one interconnected piece of information"
  it("separates a league's stacked signals with a real divider, not just a category chip", () => {
    render(<PortfolioContent data={BASE_RESPONSE} />);

    const firstSignal = screen.getByText("Trade away Test Player before Week 10").closest("div.flex.flex-col.gap-1\\.5");
    const secondSignal = screen.getByText("Test Backup is questionable for Sunday").closest("div.flex.flex-col.gap-1\\.5");

    expect((firstSignal as HTMLElement).style.borderTop).toBe("");
    expect((secondSignal as HTMLElement).style.borderTop).toContain("var(--color-border)");
  });

  // coridian_, 2026-10-18, screenshot: "not specific just says watch for no
  // reason" — a signal whose reason text alone doesn't name its subject.
  it("shows the signal's headline, not just its reason text", () => {
    render(
      <PortfolioContent
        data={{
          ...BASE_RESPONSE,
          leagues: [
            league({
              top_item: briefingItem({
                category: "watch",
                headline: "Ashton Jeanty trending down",
                reason: "Usage down 13% (high confidence) vs its earlier-season baseline.",
              }),
              top_items: [
                briefingItem({
                  category: "watch",
                  headline: "Ashton Jeanty trending down",
                  reason: "Usage down 13% (high confidence) vs its earlier-season baseline.",
                }),
              ],
            }),
          ],
        }}
      />,
    );

    expect(screen.getByText("Ashton Jeanty trending down")).toBeInTheDocument();
    expect(screen.getByText(/Usage down 13%/)).toBeInTheDocument();
  });

  // coridian_, 2026-10-18 (screenshot): Portfolio's league cards had no
  // team logo at all.
  it("renders the team's avatar image when team_avatar_url is set", () => {
    render(
      <PortfolioContent
        data={{ ...BASE_RESPONSE, leagues: [league({ team_avatar_url: "https://sleepercdn.com/avatars/abc.png" })] }}
      />,
    );

    const avatar = document.querySelector('img[src="https://sleepercdn.com/avatars/abc.png"]');
    expect(avatar).toBeInTheDocument();
  });

  it("shows the Roster Power rank in the metadata line (not a badge) when rank is outside the top 3", () => {
    render(
      <PortfolioContent
        data={{ ...BASE_RESPONSE, leagues: [league({ power_rank: 7, power_rank_tied: true })] }}
      />,
    );

    expect(screen.getByText("7-3 · Roster Power T-7")).toBeInTheDocument();
  });

  it("renders a compact player card for a signal that names a player, not just text", () => {
    render(<PortfolioContent data={BASE_RESPONSE} />);

    // route_player_id/name on the top_priority item (see briefingItem()
    // defaults) should render through BriefingItemPlayers as an identity
    // chip, not just appear inside the headline/reason prose.
    expect(screen.getAllByText("Test Player").length).toBeGreaterThan(0);
  });

  // coridian_, 2026-10-19, screenshot: "the player card location looks
  // really awkward with it being under the related text" -- for a signal
  // naming exactly one player, the compact player card must now sit in the
  // SAME row as the category pill (not stacked below the headline/reason
  // text underneath).
  it("places a single player's compact card beside the category pill, not below the text", () => {
    render(<PortfolioContent data={BASE_RESPONSE} />);

    const badge = screen.getByText("Top Priority");
    const badgeRow = badge.parentElement as HTMLElement;
    // The default top_item (briefingItem({})) names exactly one player via
    // route_player_id/name -- its card must be inside the pill's own row.
    expect(within(badgeRow).getByText("Test Player")).toBeInTheDocument();
    // The headline/reason text must NOT be in that same row -- it's the
    // sibling block below, not a row-mate of the pill+card.
    expect(within(badgeRow).queryByText("Trade away Test Player before Week 10")).not.toBeInTheDocument();
  });

  it("keeps a trade-package signal's player cards below the text, never beside the pill", () => {
    render(
      <PortfolioContent
        data={{
          ...BASE_RESPONSE,
          leagues: [
            league({
              top_item: briefingItem({
                category: "watch",
                headline: "Trade package forming",
                reason: "Two assets moving.",
                route_player_id: "",
                route_player_name: "",
                mentioned_players: [],
                presentation: {
                  trade_package: {
                    send: [{ asset_type: "player", player_id: "1", name: "Send Guy", position: "WR", team: "KC", tier: "starter" }],
                    receive: [{ asset_type: "player", player_id: "2", name: "Get Guy", position: "RB", team: "SF", tier: "starter" }],
                    value_edge: "even",
                    confidence: "medium",
                  },
                },
              }),
              top_items: [],
            }),
          ],
        }}
      />,
    );

    const badge = screen.getByText("Watch");
    const badgeRow = badge.parentElement as HTMLElement;
    expect(within(badgeRow).queryByText("Send Guy")).not.toBeInTheDocument();
    expect(screen.getByText("Send Guy")).toBeInTheDocument();
  });

  it("hides a Watch item's raw pipe-delimited reason once its player chips render", () => {
    render(
      <PortfolioContent
        data={{
          ...BASE_RESPONSE,
          leagues: [
            league({
              top_item: briefingItem({
                category: "watch",
                reason: "Test Player (RB) - starter | Backup Guy (WR) - bench",
                mentioned_players: [
                  { player_id: "4046", name: "Test Player", position: "RB", team: "SF", player_tier: "starter" },
                ],
              }),
              top_items: [
                briefingItem({
                  category: "watch",
                  reason: "Test Player (RB) - starter | Backup Guy (WR) - bench",
                  mentioned_players: [
                    { player_id: "4046", name: "Test Player", position: "RB", team: "SF", player_tier: "starter" },
                  ],
                }),
              ],
            }),
          ],
        }}
      />,
    );

    expect(screen.queryByText(/Test Player \(RB\) - starter \| Backup Guy/)).not.toBeInTheDocument();
    expect(screen.getAllByText("Test Player").length).toBeGreaterThan(0);
  });

  it("shows the health flag badge only when it isn't Stable", () => {
    render(<PortfolioContent data={{ ...BASE_RESPONSE, leagues: [league({ health_flag: "Injury-hit" })] }} />);

    expect(screen.getByText("Injury-hit")).toBeInTheDocument();
  });

  it("shows the failed-leagues note without blanking the leagues that loaded", () => {
    render(
      <PortfolioContent
        data={{
          ...BASE_RESPONSE,
          failed_leagues: [{ league_id: "league-2", league_name: "Broken League", reason: "unavailable" }],
        }}
      />,
    );

    expect(screen.getByText(/Couldn't load 1 league right now/)).toBeInTheDocument();
    expect(screen.getByText("Broken League")).toBeInTheDocument();
    expect(screen.getByText(/The Contenders — Dynasty Overlords/)).toBeInTheDocument();
  });

  // coridian_, 2026-10-19: a league stuck mid-draft landed in the same
  // scary "Couldn't load" note as a genuine failure (no linked account,
  // league gone). It should get its own calm note with a Live Draft link
  // instead, separate from the Remove-this-league failure note.
  it("shows a drafting league in its own note with a Live Draft link, not the failure note", () => {
    render(
      <PortfolioContent
        data={{
          ...BASE_RESPONSE,
          failed_leagues: [{ league_id: "league-3", league_name: "Still Drafting", reason: "empty_roster" }],
        }}
      />,
    );

    expect(screen.getByText(/Draft still in progress/)).toBeInTheDocument();
    expect(screen.getByText("Still Drafting")).toBeInTheDocument();
    // Regression: this link used to omit `?name=`, so following it landed on
    // the Header with no league-name source besides the raw id (coridian_
    // screenshot: header showed the Sleeper league_id instead of a name).
    expect(screen.getByRole("link", { name: /Watch live draft/ })).toHaveAttribute(
      "href",
      "/live-draft/league-3?name=Still%20Drafting",
    );
    expect(screen.queryByText(/Couldn't load/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /remove/i })).not.toBeInTheDocument();
  });

  // coridian_, 2026-10-19: "the couldnt load 2 leauges takes up too much
  // space and i never selected those leauges to be loaded into the site to
  // beguin with" — a league shown here can exist on the account without a
  // deliberate web-next save (Streamlit's own auto-persist can write one),
  // so the user needs a direct way to get rid of it.
  it("removes a failed league from the note when Remove succeeds", async () => {
    vi.mocked(api.removeSavedLeague).mockResolvedValue({ ok: true, reason: "" });
    render(
      <PortfolioContent
        data={{
          ...BASE_RESPONSE,
          failed_leagues: [{ league_id: "league-2", league_name: "Broken League", reason: "unavailable" }],
        }}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /remove/i }));

    await waitFor(() => expect(api.removeSavedLeague).toHaveBeenCalledWith("league-2"));
    await waitFor(() => expect(screen.queryByText("Broken League")).not.toBeInTheDocument());
  });

  it("keeps the failed league visible if Remove fails", async () => {
    vi.mocked(api.removeSavedLeague).mockResolvedValue({ ok: false, reason: "not_available" });
    render(
      <PortfolioContent
        data={{
          ...BASE_RESPONSE,
          failed_leagues: [{ league_id: "league-2", league_name: "Broken League", reason: "unavailable" }],
        }}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /remove/i }));

    await waitFor(() => expect(api.removeSavedLeague).toHaveBeenCalledWith("league-2"));
    expect(screen.getByText("Broken League")).toBeInTheDocument();
  });

  it("shows the exact Premium upsell copy for a free account", () => {
    render(
      <PortfolioContent
        data={{
          ok: true,
          is_premium: false,
          lens: "Dynasty",
          leagues: [],
          failed_leagues: [],
          upsell: {
            title: "See every league at a glance",
            body:
              "Portfolio is a Premium feature — free accounts keep one saved league, so there's nothing to aggregate yet. " +
              "Upgrade to Premium to save every league you're in and see your record, rank, and top need or " +
              "opportunity across all of them in one place.",
          },
        }}
      />,
    );

    expect(screen.getByRole("heading", { name: "See every league at a glance" })).toBeInTheDocument();
    expect(
      screen.getByText(/free accounts keep one saved league, so there's nothing to aggregate yet/),
    ).toBeInTheDocument();
  });

  it("shows the no-saved-leagues empty state", () => {
    render(<PortfolioContent data={{ ...BASE_RESPONSE, leagues: [], failed_leagues: [] }} />);

    expect(screen.getByText("No saved leagues yet")).toBeInTheDocument();
    // New-user audit: a real next step, not just a small text link.
    expect(screen.getByRole("link", { name: "Connect a league" })).toHaveAttribute("href", "/connect-league");
    expect(screen.getByTestId("sample-league-link")).toBeInTheDocument();
  });

  it("holds a still-loading league's place with a skeleton card, in saved order", () => {
    const { container } = render(
      <PortfolioContent
        data={{ ...BASE_RESPONSE, leagues: [league({ league_id: "league-2", league_name: "Second League" })] }}
        order={["league-1", "league-2"]}
        pending={[{ league_id: "league-1", league_name: "Dynasty Overlords" }]}
      />,
    );

    expect(screen.getByText("Loading Dynasty Overlords…")).toBeInTheDocument();
    const articles = Array.from(container.querySelectorAll("article"));
    expect(articles).toHaveLength(2);
    // The pending (first-saved) league stays first even though the second one loaded first.
    expect(articles[0].getAttribute("aria-busy")).toBe("true");
    expect(within(articles[1]).getByText(/The Contenders — Second League/)).toBeInTheDocument();
  });

  it("does not show the empty state while leagues are still loading", () => {
    render(
      <PortfolioContent
        data={{ ...BASE_RESPONSE, leagues: [], failed_leagues: [] }}
        order={["league-1"]}
        pending={[{ league_id: "league-1", league_name: "Dynasty Overlords" }]}
      />,
    );

    expect(screen.queryByText("No saved leagues yet")).not.toBeInTheDocument();
    expect(screen.getByText("Loading Dynasty Overlords…")).toBeInTheDocument();
  });

  it("links to /connect-league from the header so a league can be added without opening one first", () => {
    render(<PortfolioContent data={BASE_RESPONSE} />);
    expect(screen.getByRole("link", { name: "+ Add a league" })).toHaveAttribute("href", "/connect-league");
  });

  it("offers Connect a league on the empty state too", () => {
    render(<PortfolioContent data={{ ...BASE_RESPONSE, leagues: [] }} />);
    expect(screen.getByRole("link", { name: "Connect a league" })).toHaveAttribute("href", "/connect-league");
  });

  it("shows free accounts the upsell (their upgrade path), not the add link", () => {
    render(<PortfolioContent data={{ ...BASE_RESPONSE, is_premium: false }} />);
    expect(screen.queryByRole("link", { name: "+ Add a league" })).not.toBeInTheDocument();
  });
  it("reserves the same height for skeleton rows and loaded cards so nothing jumps", () => {
    const { container } = render(
      <PortfolioContent
        data={BASE_RESPONSE}
        order={["999", "s1"]}
        pending={[{ league_id: "s1", league_name: "Slow League" }]}
      />,
    );
    const min = `${PORTFOLIO_CARD_MIN_HEIGHT}px`;
    const card = container.querySelector("[data-portfolio-card]") as HTMLElement;
    const skeleton = container.querySelector("[data-portfolio-skeleton]") as HTMLElement;
    expect(card.style.minHeight).toBe(min);
    expect(skeleton.style.minHeight).toBe(min);
  });

  it("keeps saved-league order when a later league arrives first", () => {
    const { container } = render(
      <PortfolioContent
        data={BASE_RESPONSE}
        order={["slow", BASE_RESPONSE.leagues[0].league_id]}
        pending={[{ league_id: "slow", league_name: "Slow League" }]}
      />,
    );
    const rows = Array.from(container.querySelectorAll("[data-portfolio-skeleton], [data-portfolio-card]"));
    expect(rows.map((el) => el.hasAttribute("data-portfolio-skeleton"))).toEqual([true, false]);
  });

  it("offers an inline Retry for a league whose row failed, and calls back with its id", () => {
    const onRetry = vi.fn();
    render(
      <PortfolioContent
        data={{
          ...BASE_RESPONSE,
          failed_leagues: [{ league_id: "bad", league_name: "Bad League", reason: "unavailable" }],
        }}
        onRetryLeague={onRetry}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledWith("bad");
  });

  it("paints a header plus final-height skeleton cards for the instant shell", () => {
    const { container } = render(<PortfolioShell />);
    expect(screen.getByRole("heading", { name: "Your leagues" })).toBeInTheDocument();
    const skeletons = container.querySelectorAll("[data-portfolio-skeleton]");
    expect(skeletons).toHaveLength(PORTFOLIO_SHELL_SKELETON_COUNT);
    skeletons.forEach((el) => expect((el as HTMLElement).style.minHeight).toBe(`${PORTFOLIO_CARD_MIN_HEIGHT}px`));
  });
});
