import { describe, expect, it } from "vitest";

import { simNotifBadge, simNotifCursorKey, simNotifGroups, simNotifKey, simNotifMarkAllRead, simNotifParseCursor, simNotifTargetTab, simNotifTime, simNotifUnread, type SimNotification } from "./simNotifications";

const n = (seq: number, week: number, screen: SimNotification["target"]["screen"] = "home"): SimNotification => ({ id: `k:${seq}`, seq, week, kind: "k", icon: "trade", headline: `h${seq}`, target: { screen } });

describe("simNotifications", () => {
  it("unread counts items newer than the read cursor; mark-all-read never moves the cursor back", () => {
    const items = [n(30, 3), n(20, 2), n(10, 1)];
    expect(simNotifUnread(items, 0)).toBe(3);
    expect(simNotifUnread(items, 20)).toBe(1);
    expect(simNotifUnread(items, 30)).toBe(0);
    expect(simNotifMarkAllRead(5, 30)).toBe(30);
    expect(simNotifMarkAllRead(40, 30)).toBe(40);
    expect(simNotifParseCursor("12")).toBe(12);
    expect(simNotifParseCursor("junk")).toBe(0);
    expect(simNotifParseCursor(null)).toBe(0);
    expect(simNotifCursorKey("g1")).toBe("fgl:sim-notif-read:g1");
  });
  it("badge text", () => {
    expect(simNotifBadge(0)).toBe("");
    expect(simNotifBadge(4)).toBe("4");
    expect(simNotifBadge(12)).toBe("9+");
  });
  it("groups by week, newest week first and newest item first; week 0 is the draft", () => {
    const groups = simNotifGroups([n(10, 1), n(31, 3), n(30, 3), n(5, 0), n(20, 2)]);
    expect(groups.map((g) => g.label)).toEqual(["Week 3", "Week 2", "Week 1", "Draft"]);
    expect(groups[0].items.map((i) => i.seq)).toEqual([31, 30]);
    expect(simNotifTime({ week: 7 })).toBe("Wk 7");
    expect(simNotifTime({ week: 0 })).toBe("Draft");
  });
  it("deep links map to a tab (the draft opens Home)", () => {
    expect(simNotifTargetTab({ screen: "trades" })).toBe("trades");
    expect(simNotifTargetTab({ screen: "team", player_id: "p" })).toBe("team");
    expect(simNotifTargetTab({ screen: "players" })).toBe("players");
    expect(simNotifTargetTab({ screen: "draft" })).toBe("home");
    expect(simNotifTargetTab({ screen: "home" })).toBe("home");
  });
  it("the refetch key changes only when the game changed", () => {
    const g = { status: "in_season", week: 4, pending: { inbox: 2, lineup_warnings: 1, claims: 0 } };
    expect(simNotifKey(g)).toBe(simNotifKey({ ...g }));
    expect(simNotifKey(g)).not.toBe(simNotifKey({ ...g, week: 5 }));
    expect(simNotifKey(g)).not.toBe(simNotifKey({ ...g, pending: { inbox: 3, lineup_warnings: 1, claims: 0 } }));
    expect(simNotifKey(g, 1)).not.toBe(simNotifKey(g, 0));
  });
});
