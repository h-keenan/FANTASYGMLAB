import { render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DashboardAlerts } from "./DashboardAlerts";
import { api, type AlertItem } from "@/lib/api";

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
    await waitFor(() => expect(screen.getByText(/All caught up/)).toBeInTheDocument());
    expect(screen.queryByTestId("dashboard-alerts-count")).toBeNull();
  });
});
