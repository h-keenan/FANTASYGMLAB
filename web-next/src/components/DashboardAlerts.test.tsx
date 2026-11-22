import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DashboardAlerts } from "./DashboardAlerts";
import { api, type AlertItem, type BriefingItem } from "@/lib/api";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/context/AuthContext", () => ({ useAuth: () => ({ session: { user: { id: "u1" } } }) }));

function alert(key: string, read: boolean, over: Partial<AlertItem> = {}): AlertItem {
  return {
    title: `Alert ${key}`,
    link: null,
    source: "",
    summary: "",
    published_ts: Date.now() / 1000,
    event_type: "injury/status",
    speculative: false,
    alert_key: key,
    read,
    matched_player: `Player ${key}`,
    matched_player_id: `p-${key}`,
    matched_player_position: "RB",
    matched_player_team: "SF",
    matched_player_tier: "starter",
    relevance_reason: "",
    roster_relationship: "starter",
    ...over,
  } as AlertItem;
}

describe("DashboardAlerts", () => {
  it("shows the unread count as a badge on the Alerts heading", async () => {
    vi.spyOn(api, "getLeagueAlerts").mockResolvedValue({ ok: true, reason: "", items: [alert("a", false), alert("b", false), alert("c", true)] });
    render(<DashboardAlerts leagueId="L1" leagueName="League" />);
    await waitFor(() => expect(screen.getByTestId("dashboard-alerts-count")).toHaveTextContent("2"));
    expect(screen.getByTestId("dashboard-alerts")).toBeInTheDocument();
    expect(document.getElementById("alerts")).not.toBeNull();
  });

  it("has no badge when everything is read", async () => {
    vi.spyOn(api, "getLeagueAlerts").mockResolvedValue({ ok: true, reason: "", items: [alert("c", true)] });
    render(<DashboardAlerts leagueId="L1" leagueName="League" />);
    await waitFor(() => expect(screen.getByTestId("dashboard-alerts")).toHaveTextContent("Alert c"));
    expect(screen.queryByTestId("dashboard-alerts-count")).toBeNull();
  });

  it("renders a rostered starter's news as an action row (avatar, one line, Swap that opens the lineup planner)", async () => {
    vi.spyOn(api, "getLeagueAlerts").mockResolvedValue({ ok: true, reason: "", items: [alert("a", false, { title: "Reyes ruled OUT", matched_player: "Jordan Reyes", matched_player_id: "p1" })] });
    render(<DashboardAlerts leagueId="L1" leagueName="League" />);
    const row = await screen.findByTestId("alert-row");
    expect(row).toHaveTextContent("Reyes ruled OUT");
    const button = within(row).getByTestId("alert-primary");
    expect(button).toHaveTextContent("Swap");
    expect(button).toHaveAttribute("href", expect.stringContaining("/matchup/L1?name=League&plan=all"));
  });

  it("never shows news with no rostered player behind it, and a bench player's news is a Read link", async () => {
    vi.spyOn(api, "getLeagueAlerts").mockResolvedValue({
      ok: true,
      reason: "",
      items: [
        alert("league", false, { title: "League-wide headline", matched_player: null, matched_player_id: null, roster_relationship: null }),
        alert("bench", false, { title: "Bench WR limited", roster_relationship: "bench", link: "https://example.com/story" }),
      ],
    });
    render(<DashboardAlerts leagueId="L1" leagueName="League" />);
    const rows = await screen.findAllByTestId("alert-row");
    expect(rows).toHaveLength(1);
    expect(screen.getByTestId("dashboard-alerts")).not.toHaveTextContent("League-wide headline");
    expect(within(rows[0]).getByTestId("alert-primary")).toHaveTextContent("Read");
    expect(within(rows[0]).getByTestId("alert-primary")).toHaveAttribute("href", "https://example.com/story");
  });

  it("folds the watchlist into All alerts", async () => {
    vi.spyOn(api, "getLeagueAlerts").mockResolvedValue({ ok: true, reason: "", items: [alert("a", false, { title: "Reyes ruled OUT", matched_player: "Jordan Reyes", matched_player_id: "p1" })] });
    const watch = [{ category: "watch", headline: "Watchlist: D. Mason", reason: "Now a free agent", destination: "waivers", route_player_id: "p3", route_player_name: "D. Mason", route_player_position: "WR", route_player_team: "SF", route_player_tier: "starter", mentioned_players: [], recommendation_id: "w1" }] as unknown as BriefingItem[];
    render(<DashboardAlerts leagueId="L1" leagueName="League" watchItems={watch} />);
    fireEvent.click(await screen.findByTestId("alerts-see-all"));
    expect(await screen.findByTestId("watchlist-alerts")).toBeInTheDocument();
  });
});
