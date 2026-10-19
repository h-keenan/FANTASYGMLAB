import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AlertsContent } from "./AlertsContent";
import type { AlertItem, AlertsResponse } from "@/lib/api";
import { api } from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      markAlertRead: vi.fn().mockResolvedValue({ ok: true }),
    },
  };
});

function alert(overrides: Partial<AlertItem>): AlertItem {
  return {
    title: "Test player ruled out for Week 7",
    link: "https://example.com/article",
    source: "Rotoworld",
    summary: "Will not play Sunday due to a hamstring injury.",
    published_ts: Date.now() / 1000 - 3600,
    event_type: "injury/status",
    speculative: false,
    alert_key: "key-1",
    read: false,
    matched_player: "Test Player",
    matched_player_id: "4046",
    matched_player_position: "RB",
    matched_player_team: "SF",
    matched_player_tier: "starter",
    relevance_reason: "On your roster",
    roster_relationship: "starter",
    ...overrides,
  };
}

const BASE_RESPONSE: AlertsResponse = {
  ok: true,
  reason: "",
  items: [alert({})],
};

describe("AlertsContent", () => {
  it("renders the league name, grouped event type, and the alert's headline/player identity", () => {
    const { container } = render(<AlertsContent leagueId="league-1" leagueName="Dynasty Overlords" data={BASE_RESPONSE} />);

    expect(screen.getByRole("heading", { name: "Dynasty Overlords" })).toBeInTheDocument();
    expect(screen.getByText("Injury / Status")).toBeInTheDocument();
    expect(screen.getByText("Test player ruled out for Week 7")).toBeInTheDocument();
    expect(screen.getByText("Test Player")).toBeInTheDocument();
    expect(screen.getByText("Starter")).toBeInTheDocument();
    expect(screen.getByText("Source: Rotoworld")).toBeInTheDocument();
    // coridian_, 2026-10-19 (screenshot): "why is there no player card on
    // these?"
    expect(container.querySelector('img[src*="4046.jpg"]')).toBeInTheDocument();
  });

  it("marks an alert read and calls the API when the row is opened", () => {
    render(<AlertsContent leagueId="league-1" leagueName="Dynasty Overlords" data={BASE_RESPONSE} />);

    fireEvent.click(screen.getByRole("link", { name: "Test player ruled out for Week 7" }));

    expect(api.markAlertRead).toHaveBeenCalledWith("league-1", "key-1");
  });

  // coridian_: "you need to be able to click on the players (needs to be
  // compact player card)" — tapping the player chip must not also fire the
  // row's own open/read-marking handler underneath it.
  it("tapping the player chip does not also mark the alert as read", () => {
    render(<AlertsContent leagueId="league-1" leagueName="Dynasty Overlords" data={BASE_RESPONSE} />);

    fireEvent.click(screen.getByRole("button", { name: /Test Player/ }));

    expect(api.markAlertRead).not.toHaveBeenCalled();
  });

  it("shows the unconfirmed badge for speculative alerts", () => {
    render(
      <AlertsContent
        leagueId="league-1"
        leagueName="Dynasty Overlords"
        data={{ ok: true, reason: "", items: [alert({ speculative: true })] }}
      />,
    );

    expect(screen.getByText("Unconfirmed / speculative")).toBeInTheDocument();
  });

  it("shows the empty state when there are no alerts", () => {
    render(<AlertsContent leagueId="league-1" leagueName="Dynasty Overlords" data={{ ok: true, reason: "", items: [] }} />);

    expect(screen.getByText("All quiet. No relevant news for your roster right now.")).toBeInTheDocument();
  });

  it("shows the not-ready message instead of the feed when reason is set", () => {
    render(
      <AlertsContent
        leagueId="league-1"
        leagueName="Dynasty Overlords"
        data={{ ok: true, reason: "not_a_member_of_league", items: [] }}
      />,
    );

    expect(screen.getByText(/Alerts needs to know which players are yours/)).toBeInTheDocument();
  });
});
