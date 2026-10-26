import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { NewsContent } from "./NewsContent";
import type { NewsItem, NewsResponse } from "@/lib/api";

// A real Date.now()-relative published_ts ("1 hour ago") plus the
// component's own default `nowMs` (also real Date.now(), see
// groupNewsByDate) made every assertion of "Today" genuinely flaky right
// around midnight UTC — CI runs in UTC, and "1 hour ago" crosses into
// yesterday for roughly the first hour of every day. Pinning the clock
// mid-day, far from any boundary, makes every item below deterministically
// "Today" regardless of when the suite actually runs.
beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-06-15T12:00:00Z"));
});

afterEach(() => {
  vi.useRealTimers();
});

function newsItem(overrides: Partial<NewsItem>): NewsItem {
  return {
    title: "Star RB (knee) questionable for Sunday",
    link: "https://example.com/injury-1",
    source: "ESPN",
    summary: "The team's RB1 was limited in practice with a knee issue.",
    published_ts: Date.now() / 1000 - 3600,
    event_type: "injury/status",
    speculative: false,
    ...overrides,
  };
}

describe("NewsContent", () => {
  it("renders the page header and a grouped event-type card", () => {
    const data: NewsResponse = { ok: true, items: [newsItem({})] };
    render(<NewsContent data={data} />);

    expect(screen.getByRole("heading", { name: "News" })).toBeInTheDocument();
    expect(screen.getByText("Today")).toBeInTheDocument();
    expect(screen.getByText("Injury / Status")).toBeInTheDocument();
    expect(screen.getByText("Star RB (knee) questionable for Sunday")).toBeInTheDocument();
    expect(screen.getByText("ESPN")).toBeInTheDocument();
  });

  it("shows a single-player identity chip when the item resolved to one player", () => {
    const data: NewsResponse = {
      ok: true,
      items: [
        newsItem({
          matched_player: "Justin Jefferson",
          matched_player_id: "6794",
          matched_player_position: "WR",
          matched_player_team: "MIN",
        }),
      ],
    };
    const { container } = render(<NewsContent data={data} />);

    expect(screen.getByText("Justin Jefferson")).toBeInTheDocument();
    expect(screen.getByText("WR")).toBeInTheDocument();
    expect(screen.getByText("MIN")).toBeInTheDocument();
    // coridian_, 2026-10-19 (screenshot, same gap on Alerts): "why is
    // there no player card on these?"
    expect(container.querySelector('img[src*="6794.jpg"]')).toBeInTheDocument();
  });

  it("shows both stacked identity chips for a two-player item", () => {
    const data: NewsResponse = {
      ok: true,
      items: [
        newsItem({
          title: "Davante Adams and DeAndre Hopkins swap teams in trade",
          event_type: "transaction",
          matched_players: [
            { matched_player: "Davante Adams", matched_player_id: "2133", matched_player_position: "WR", matched_player_team: "LAR" },
            { matched_player: "DeAndre Hopkins", matched_player_id: "1426", matched_player_position: "WR" },
          ],
        }),
      ],
    };
    render(<NewsContent data={data} />);

    expect(screen.getByText("Davante Adams")).toBeInTheDocument();
    expect(screen.getByText("DeAndre Hopkins")).toBeInTheDocument();
    expect(screen.getByText("LAR")).toBeInTheDocument();
  });

  it("renders no identity row for a team-level story with no matched player", () => {
    const data: NewsResponse = {
      ok: true,
      items: [newsItem({ title: "Team fires offensive coordinator after bye week", matched_player: undefined })],
    };
    render(<NewsContent data={data} />);

    expect(screen.getByText("Team fires offensive coordinator after bye week")).toBeInTheDocument();
    expect(screen.queryByText("WR")).not.toBeInTheDocument();
  });

  it("shows the unconfirmed/speculative badge", () => {
    const data: NewsResponse = { ok: true, items: [newsItem({ speculative: true })] };
    render(<NewsContent data={data} />);

    expect(screen.getByText("Unconfirmed / speculative")).toBeInTheDocument();
  });

  it("groups items by date bucket before event type", () => {
    const now = new Date();
    // Noon yesterday is unambiguously within [startOfYesterday, startOfToday)
    // regardless of what time of day the test itself runs at.
    const yesterdayNoon = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1, 12, 0, 0).getTime() / 1000;
    const data: NewsResponse = {
      ok: true,
      items: [
        newsItem({ title: "Today's injury update", published_ts: Date.now() / 1000 - 60, event_type: "injury/status" }),
        newsItem({
          title: "Yesterday's trade",
          link: "https://example.com/trade-1",
          published_ts: yesterdayNoon,
          event_type: "transaction",
        }),
      ],
    };
    render(<NewsContent data={data} />);

    expect(screen.getByText("Today")).toBeInTheDocument();
    expect(screen.getByText("Yesterday")).toBeInTheDocument();
  });

  it("shows the empty state when there are no items", () => {
    const data: NewsResponse = { ok: true, items: [] };
    render(<NewsContent data={data} />);

    expect(screen.getByText(/No news right now/)).toBeInTheDocument();
  });

  it("explains a cold start instead of a bare empty page", () => {
    const data: NewsResponse = {
      ok: true,
      items: [],
      status: { state: "warming_up", last_updated_ts: 0, message: "News is loading for the first time." },
    };
    render(<NewsContent data={data} />);

    expect(screen.getByText(/News is warming up/)).toBeInTheDocument();
    expect(screen.getByText(/loading for the first time/)).toBeInTheDocument();
  });
});
