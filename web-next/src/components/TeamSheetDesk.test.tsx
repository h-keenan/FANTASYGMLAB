import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

const sheet = {
  ok: true,
  reason: "",
  roster_id: "3",
  team: { team_name: "Big Dogs", owner_name: "Zach K", avatar_url: null },
  record: { wins: 9, losses: 3, ties: 0, label: "9-3", standing_rank: 2, points_for: 1400.5, playoff_status: "in" },
  power_rank: 1,
  teams: 12,
  streak: "W4",
  projected_total: 121.4,
  next_game: { week: 13, opponent: { roster_id: "5", name: "Rival FC" } },
  positions: [
    { pos: "QB", level: "strength", rank: 1, teams: 12, depth: 3 },
    { pos: "TE", level: "need", rank: 11, teams: 12, depth: 1 },
  ],
  strengths: ["QB"],
  needs: ["TE"],
  injuries: [{ player_id: "9", name: "Hurt Guy", position: "WR", team: "KC", age: 25, injury_status: "Questionable", value: 50, slot: "bench" }],
  roster: [
    { player_id: "1", name: "Starter One", position: "QB", team: "BUF", age: 28, injury_status: "", value: 90, slot: "starter" },
    { player_id: "9", name: "Hurt Guy", position: "WR", team: "KC", age: 25, injury_status: "Questionable", value: 50, slot: "bench" },
  ],
  history: [{ season: "2025", league_id: "L25", wins: 8, losses: 6, ties: 0, points_for: 1300, place: 3, of: 12 }],
};

const pro = {
  ok: true,
  is_premium: true,
  upsell: null,
  manager: {
    team_name: "Big Dogs",
    owner_handle: "zk",
    headline: null,
    sample: { trades: 6, wire_moves: 2, seasons: 2 },
    signals: {
      trade_frequency: { status: "ok", label: "trades_more_than_most", summary: "Trades more than most.", sample_size: 6, min_sample: 5, evidence: [] },
    },
  },
  recent_trades: [],
};
const free = { ok: true, is_premium: false, upsell: { title: "See how they trade", body: "" }, manager: null };

async function mount(detail: unknown) {
  vi.resetModules();
  vi.doMock("@/lib/api", () => ({
    api: { getTeamSheet: () => Promise.resolve(sheet), getManagerTendencyDetail: () => Promise.resolve(detail), getTeamProfile: () => new Promise(() => {}) },
  }));
  const { ManagerProfileSheet } = await import("./ManagerProfileSheet");
  render(<ManagerProfileSheet leagueId="1" rosterId={3} teamName="Big Dogs" ownerName="Zach K" onClose={() => {}} />);
}

describe("Desk team sheet", () => {
  afterEach(() => {
    vi.doUnmock("@/lib/api");
    window.sessionStorage.clear();
  });

  it("shows real header chips, tiles, streak, strengths and needs, and injuries", async () => {
    await mount(pro);
    expect(await screen.findByText("Power #1")).toBeTruthy();
    expect(screen.getByText("IN")).toBeTruthy();
    expect(screen.getByText("Managed by Zach K")).toBeTruthy();
    expect(screen.getByText("TRADE HAPPY")).toBeTruthy();
    expect(screen.getByText("Trades more than most.")).toBeTruthy();
    expect(screen.getByText("9-3")).toBeTruthy();
    expect(screen.getByText("#2")).toBeTruthy();
    expect(screen.getByText("121.4")).toBeTruthy();
    expect(screen.getByText("W4")).toBeTruthy();
    expect(screen.getByText(/Week 13 vs Rival FC/)).toBeTruthy();
    expect(screen.getByText("Strength")).toBeTruthy();
    expect(screen.getByText("#1 of 12 · depth 3")).toBeTruthy();
    expect(screen.getByText("Need")).toBeTruthy();
    expect(screen.getByText("Hurt Guy")).toBeTruthy();
  });

  it("lists the roster and past seasons", async () => {
    await mount(pro);
    fireEvent.click(await screen.findByRole("tab", { name: "Roster" }));
    expect(await screen.findByText("Starter One")).toBeTruthy();
    fireEvent.click(screen.getByRole("tab", { name: "History" }));
    expect(await screen.findByText("2025")).toBeTruthy();
    expect(screen.getByText("8-6 · #3 of 12")).toBeTruthy();
  });

  it("keeps the sheet for Free users but swaps the trade style for the upsell", async () => {
    await mount(free);
    expect(await screen.findByText("9-3")).toBeTruthy();
    expect(screen.getByText("TRADE STYLE · PRO")).toBeTruthy();
    expect(screen.getByText("See how they trade")).toBeTruthy();
    expect(screen.queryByText("TRADE HAPPY")).toBeNull();
  });
});
