import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DashboardAlerts } from "./DashboardAlerts";
import { api, type AlertItem, type BriefingItem } from "@/lib/api";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/context/AuthContext", () => ({ useAuth: () => ({ session: { user: { id: "u1" } } }) }));

function alert(key: string, read: boolean): AlertItem {
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
    matched_player: "",
    matched_player_id: "",
    matched_player_position: "",
    matched_player_team: "",
    matched_player_tier: "",
    relevance_reason: "",
    roster_relationship: "starter",
  } as AlertItem;
}

describe("DashboardAlerts", () => {
  it("shows the unread count as a badge on the collapsed Alerts section", async () => {
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

  it("collapses to avatars of the players involved, the newest headline and how many more, with the watchlist folded in", async () => {
    vi.spyOn(api, "getLeagueAlerts").mockResolvedValue({
      ok: true,
      reason: "",
      items: [
        { ...alert("a", false), title: "Reyes ruled OUT", matched_player: "Jordan Reyes", matched_player_id: "p1", matched_player_position: "RB" },
        { ...alert("b", false), title: "Bell limited in practice", matched_player: "Marcus Bell", matched_player_id: "p2", matched_player_position: "WR" },
      ],
    });
    const watch = [{ category: "watch", headline: "Watchlist: D. Mason", reason: "Now a free agent", destination: "waivers", route_player_id: "p3", route_player_name: "D. Mason", route_player_position: "WR", route_player_team: "SF", route_player_tier: "starter", mentioned_players: [], recommendation_id: "w1" }] as unknown as BriefingItem[];
    render(<DashboardAlerts leagueId="L1" leagueName="League" watchItems={watch} />);
    await waitFor(() => expect(screen.getByTestId("dashboard-alerts-avatars").children).toHaveLength(3));
    const section = screen.getByTestId("dashboard-alerts");
    expect(section).toHaveTextContent("2 new");
    expect(section).toHaveTextContent("Reyes ruled OUT");
    expect(section).toHaveTextContent("+2 more");
  });
});
