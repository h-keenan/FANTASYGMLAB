import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { AlertsBell } from "./AlertsDropdown";
import { api, type AlertItem, type AlertsResponse } from "@/lib/api";

vi.mock("@/context/AuthContext", () => ({
  useAuth: () => ({ session: { user: { id: "user-1" } } }),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      getLeagueAlerts: vi.fn(),
      markAlertRead: vi.fn().mockResolvedValue({ ok: true }),
    },
  };
});

function alert(overrides: Partial<AlertItem>): AlertItem {
  return {
    title: "Ruled out",
    link: null,
    source: "Rotoworld",
    summary: null,
    published_ts: Date.now() / 1000 - 3600,
    event_type: "injury/status",
    speculative: false,
    alert_key: "k1",
    read: false,
    matched_player: null,
    matched_player_id: null,
    matched_player_position: null,
    matched_player_team: null,
    matched_player_tier: null,
    relevance_reason: "",
    roster_relationship: null,
    ...overrides,
  } as AlertItem;
}

function respond(items: AlertItem[]) {
  const data: AlertsResponse = { ok: true, reason: "", items };
  vi.mocked(api.getLeagueAlerts).mockResolvedValue(data);
}

function renderBell() {
  return render(<AlertsBell leagueId="L1" alertsHref="/alerts/L1" iconProps={{}} />);
}

beforeEach(() => {
  window.localStorage.clear();
  vi.mocked(api.getLeagueAlerts).mockReset();
  vi.mocked(api.markAlertRead).mockClear();
});

describe("AlertsBell", () => {
  it("fetches nothing until opened, then lists alerts with an unread badge", async () => {
    respond([alert({}), alert({ alert_key: "k2", title: "Traded", read: true })]);
    renderBell();
    expect(api.getLeagueAlerts).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Alerts" }));
    expect(await screen.findByText("Ruled out")).toBeInTheDocument();
    expect(screen.getByText("Traded")).toBeInTheDocument();
    expect(screen.getByRole("dialog", { name: "Alerts" })).toBeInTheDocument();
    expect(screen.getByTestId("alerts-unread-badge")).toHaveTextContent("1");
  });

  it("closes with Esc, the X and the backdrop", async () => {
    respond([alert({ read: true })]);
    renderBell();
    fireEvent.click(screen.getByRole("button", { name: "Alerts" }));
    await screen.findByText("Ruled out");
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Alerts" }));
    fireEvent.click(screen.getByRole("button", { name: "Close alerts" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Alerts" }));
    fireEvent.click(screen.getByTestId("alerts-backdrop"));
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("marks a tapped alert read through the sync and clears its badge", async () => {
    respond([alert({})]);
    renderBell();
    fireEvent.click(screen.getByRole("button", { name: "Alerts" }));
    fireEvent.click(await screen.findByText("Ruled out"));
    await waitFor(() => expect(api.markAlertRead).toHaveBeenCalledWith("L1", "k1"));
    expect(screen.queryByTestId("alerts-unread-badge")).toBeNull();
  });

  it("marks everything shown as read on close", async () => {
    respond([alert({}), alert({ alert_key: "k2", title: "Traded" })]);
    renderBell();
    fireEvent.click(screen.getByRole("button", { name: "Alerts" }));
    await screen.findByText("Traded");
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "Close alerts" }));
    });
    await waitFor(() => expect(api.markAlertRead).toHaveBeenCalledTimes(2));
    expect(screen.queryByTestId("alerts-unread-badge")).toBeNull();
  });

  it("links to the full Alerts page", async () => {
    respond([alert({ read: true })]);
    renderBell();
    fireEvent.click(screen.getByRole("button", { name: "Alerts" }));
    await screen.findByText("Ruled out");
    expect(screen.getByRole("link", { name: /View all alerts/ })).toHaveAttribute("href", "/alerts/L1");
  });

  it("shows the empty state when there are no alerts", async () => {
    respond([]);
    renderBell();
    fireEvent.click(screen.getByRole("button", { name: "Alerts" }));
    expect(await screen.findByTestId("empty-state")).toBeInTheDocument();
  });
});
