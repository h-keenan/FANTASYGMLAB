import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SimNotificationBell } from "@/components/SimNotificationBell";
import type { SimNotification } from "@/lib/simNotifications";

const item = (seq: number, week: number, headline: string, screen: SimNotification["target"]["screen"], icon = "trade"): SimNotification => ({ id: `k:${seq}`, seq, week, kind: "k", icon, headline, target: { screen } });

function setup(unread = 2, items: SimNotification[] = [item(30, 7, "Rats want Quinn Moore", "trades"), item(20, 7, "Marcus Lane is out 3 weeks", "team", "injury"), item(10, 6, "Week 6 recap is ready", "home", "matchup")]) {
  const markAllRead = vi.fn();
  const onOpenTab = vi.fn();
  const notif = { items, unread, cursor: 10, markAllRead };
  render(<SimNotificationBell notif={notif} onOpenTab={onOpenTab} />);
  return { markAllRead, onOpenTab };
}

describe("SimNotificationBell", () => {
  it("shows the unread badge, caps it at 9+, and says nothing when everything is read", () => {
    setup(2);
    expect(screen.getByRole("button", { name: "Notifications, 2 unread" })).toBeInTheDocument();
    expect(screen.getByTestId("sim-bell-badge")).toHaveTextContent("2");
  });

  it("opens a week-grouped list, marks everything read on open, and a row deep-links to its screen", () => {
    const { markAllRead, onOpenTab } = setup(2);
    fireEvent.click(screen.getByTestId("sim-bell"));
    expect(markAllRead).toHaveBeenCalled();
    expect(screen.getByRole("dialog", { name: "Notifications" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Week 7" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Week 6" })).toBeInTheDocument();
    expect(screen.getAllByText("Wk 7").length).toBe(2);
    fireEvent.click(screen.getByRole("button", { name: /Rats want Quinn Moore/ }));
    expect(onOpenTab).toHaveBeenCalledWith("trades");
  });

  it("the injury row opens Team; an empty list explains itself", () => {
    const { onOpenTab } = setup(1);
    fireEvent.click(screen.getByTestId("sim-bell"));
    fireEvent.click(screen.getByRole("button", { name: /Marcus Lane is out/ }));
    expect(onOpenTab).toHaveBeenCalledWith("team");
  });

  it("with no items: an explanation and no badge", () => {
    setup(0, []);
    expect(screen.queryByTestId("sim-bell-badge")).toBeNull();
    fireEvent.click(screen.getByTestId("sim-bell"));
    expect(screen.getByText(/Nothing yet/)).toBeInTheDocument();
  });
});
