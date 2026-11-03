import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { SinceLastVisitStrip } from "./SinceLastVisitStrip";
import { api } from "@/lib/api";
import { lastVisitStorageKey } from "@/lib/sinceLastVisit";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, api: { ...actual.api, getLeagueHistory: vi.fn(), getLeagueAlerts: vi.fn() } };
});

const DAY = 86_400_000;

describe("SinceLastVisitStrip", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.clearAllMocks();
  });

  it("shows nothing and makes no request on a first visit, but starts the clock", () => {
    render(<SinceLastVisitStrip userId="u1" leagueId="L1" leagueName="Test League" />);
    expect(screen.queryByTestId("since-last-visit")).toBeNull();
    expect(api.getLeagueHistory).not.toHaveBeenCalled();
    expect(window.localStorage.getItem(lastVisitStorageKey("u1", "L1"))).toContain("since");
  });

  it("summarises real league activity and news since the previous visit", async () => {
    const last = Date.now() - 2 * DAY;
    window.localStorage.setItem(lastVisitStorageKey("u1", "L1"), JSON.stringify({ since: last - DAY, last }));
    vi.mocked(api.getLeagueHistory).mockResolvedValue({
      ok: true, seasons: [], selected_league_id: "L1", reason: "",
      transactions: [
        { transaction_id: "a", season: "2026", league_id: "L1", week: 8, timestamp: Date.now() - DAY, type: "trade", draft_picks: [], sides: [], grade: null },
        { transaction_id: "b", season: "2026", league_id: "L1", week: 8, timestamp: last - 5, type: "trade", draft_picks: [], sides: [], grade: null },
      ],
    } as never);
    vi.mocked(api.getLeagueAlerts).mockResolvedValue({
      ok: true, reason: "",
      items: [{ title: "Out", link: null, source: null, summary: null, published_ts: (Date.now() - DAY) / 1000, event_type: "injury/status", speculative: false, alert_key: "k", read: false }],
    } as never);
    render(<SinceLastVisitStrip userId="u1" leagueId="L1" leagueName="Test League" />);
    const strip = await screen.findByTestId("since-last-visit");
    expect(strip).toHaveTextContent("1 trade in your league");
    expect(strip).toHaveTextContent("1 update, 1 injury/status");
    expect(screen.getByText("New trades").closest("a")).toHaveAttribute("href", "/league-recaps/L1?name=Test%20League");
    expect(screen.getByText("Your players").closest("a")).toHaveAttribute("href", "/alerts/L1?name=Test%20League");
  });

  it("renders nothing when both reads fail", async () => {
    const last = Date.now() - 2 * DAY;
    window.localStorage.setItem(lastVisitStorageKey("u1", "L1"), JSON.stringify({ since: last, last }));
    vi.mocked(api.getLeagueHistory).mockRejectedValue(new Error("down"));
    vi.mocked(api.getLeagueAlerts).mockRejectedValue(new Error("down"));
    render(<SinceLastVisitStrip userId="u1" leagueId="L1" leagueName="Test League" />);
    await waitFor(() => expect(api.getLeagueAlerts).toHaveBeenCalled());
    expect(screen.queryByTestId("since-last-visit")).toBeNull();
  });
});
