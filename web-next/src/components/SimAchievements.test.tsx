import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SimAchievementsModule, SimBadgeChips, SimTrophyRow } from "./SimAchievements";
import type { SimAchievement } from "@/lib/simAchievements";

const ach = (over: Partial<SimAchievement> = {}): SimAchievement => ({
  id: "x:1", key: "x", scope: "season", rarity: "common", tone: "good", icon: "check", name: "X", detail: "Detail text", unlocked: true,
  season_no: 3, year: 2028, season_label: "S3 2028", week: 14, at: 314, progress: null, tier: null, player: null, ...over,
});

describe("SimAchievementsModule", () => {
  const payload = {
    items: [
      ach({ id: "perfect:3", name: "Perfect Season", rarity: "epic", detail: "14-0 and the title" }),
      ach({ id: "winless:2", name: "Winless Season", rarity: "rare", tone: "bad", season_no: 2, season_label: "S2 2027", at: 214 }),
      ach({ id: "wins50", name: "50 Career Wins", scope: "career", unlocked: false, rarity: "rare", progress: { current: 30, target: 50, text: "30 of 50 wins" }, at: null, week: null }),
    ],
  };

  it("shows unlocked badges with the shared season label and locked ones with progress", () => {
    render(<SimAchievementsModule payload={payload} seasonNo={3} openOnPhone />);
    const rows = screen.getAllByTestId("achievement-row");
    expect(rows).toHaveLength(3);
    expect(within(rows[0]).getByText("Perfect Season")).toBeTruthy();
    expect(within(rows[0]).getByText("S3 2028 · Wk 14")).toBeTruthy();
    expect(within(rows[0]).getByText("Epic")).toBeTruthy();
    expect(rows[2].getAttribute("data-unlocked")).toBe("false");
    expect(within(rows[2]).getByText("30 of 50 wins")).toBeTruthy();
    expect(screen.getByRole("progressbar", { name: "50 Career Wins progress" }).getAttribute("aria-valuenow")).toBe("60");
  });

  it("opens a badge's detail on tap and closes it again", () => {
    render(<SimAchievementsModule payload={payload} seasonNo={3} openOnPhone />);
    const row = screen.getAllByTestId("achievement-row")[0];
    expect(screen.queryByTestId("achievement-detail")).toBeNull();
    fireEvent.click(row);
    expect(screen.getByTestId("achievement-detail").textContent).toContain("14-0 and the title");
    fireEvent.click(row);
    expect(screen.queryByTestId("achievement-detail")).toBeNull();
  });

  it("renders nothing for an older server and an empty hint for a fresh game", () => {
    const { container } = render(<SimAchievementsModule payload={undefined} />);
    expect(container.firstChild).toBeNull();
    render(<SimAchievementsModule payload={{ items: [] }} openOnPhone id="empty" />);
    expect(screen.getByText(/Nothing earned yet/)).toBeTruthy();
  });
});

describe("team and player rows", () => {
  it("renders trophies only when there are titles", () => {
    const { container } = render(<SimTrophyRow rows={[]} />);
    expect(container.firstChild).toBeNull();
    render(<SimTrophyRow rows={[{ label: "S3 2028", record: "12-2" }]} />);
    expect(screen.getByTestId("sim-trophy-row").textContent).toContain("S3 2028");
  });
  it("renders badge chips with the season", () => {
    render(<SimBadgeChips items={[ach({ name: "League MVP" })]} />);
    expect(screen.getByTestId("sim-badge-chips").textContent).toContain("League MVP");
    expect(screen.getByTestId("sim-badge-chips").textContent).toContain("S3 2028");
  });
});
