import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SimWeekRecapStory } from "@/components/SimRecapStory";
import type { SimCtx } from "@/components/SimGameParts";
import type { SimGamePlayer, SimWeekRecap } from "@/lib/simGame";

const player = (id: string, name: string, pos: string) => ({ id, name, pos, team: "KC", age: 25, bye_week: 9, status: "healthy", out_weeks: 0, projection: 12, ros_mean: 12, value: 50, adp: 20, overall: 70 }) as unknown as SimGamePlayer;
const recap = {
  week: 4,
  kind: "regular",
  round: null,
  your_game: {
    opponent_id: "7",
    opponent_name: "Rats",
    your_pts: 128.4,
    opp_pts: 109.7,
    result: "win",
    starters: [{ slot: "QB", player: player("q", "Quinn Moore", "QB"), pts: 25, flag: null }, { slot: "WR", player: player("w", "Wade Hall", "WR"), pts: 0, flag: "bye" }],
    optimal_pts: 134.2,
    efficiency: 0.96,
  },
  scores: [{ home: "1", away: "2", home_pts: 102, away_pts: 95, winner: "1" }],
  standings: [{ team_id: "1", name: "Goats" }, { team_id: "2", name: "Brigade" }],
  injuries: [],
  season_complete: false,
  champion: null,
  next_week: 5,
} as unknown as SimWeekRecap;
const openPlayer = vi.fn();
const ctx = {
  game: { status: "in_season", week: 5, settings: { mode: "redraft" }, you: { team_id: "9", name: "Me" }, trade_deadline_week: 10, pending: { lineup_warnings: 1, inbox: 2 }, this_week: { opponent: { team_id: "3", name: "Titans" }, bye: false, your_projection: 121.4, opponent_projection: 117.9 } },
  openPlayer,
} as unknown as SimCtx;

describe("SimWeekRecapStory", () => {
  it("shows Result, Matchup, Injuries, League, Next as story pages with a Fix lineup action and a final CTA", () => {
    const onClose = vi.fn();
    const onFix = vi.fn();
    render(<SimWeekRecapStory recap={recap} index={0} total={1} ctx={ctx} onNext={() => {}} onClose={onClose} onFixLineup={onFix} />);
    const labels = screen.getAllByRole("button", { name: /^Go to / }).map((b) => b.getAttribute("aria-label"));
    expect(labels).toHaveLength(5);
    expect(screen.getByText("Won by 18.7")).toBeInTheDocument();
    const dialog = screen.getByRole("dialog");
    fireEvent.keyDown(dialog, { key: "ArrowRight" });
    expect(screen.getByText("96%")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Quinn Moore.*Open player details/ }));
    expect(openPlayer).toHaveBeenCalledTimes(1);
    fireEvent.keyDown(dialog, { key: "ArrowRight" });
    fireEvent.click(screen.getByRole("button", { name: "Fix lineup" }));
    expect(onFix).toHaveBeenCalledTimes(1);
    fireEvent.keyDown(dialog, { key: "ArrowRight" });
    expect(screen.getByText("Top score: Goats")).toBeInTheDocument();
    fireEvent.keyDown(dialog, { key: "ArrowRight" });
    expect(screen.getByText("Titans")).toBeInTheDocument();
    expect(screen.getByText("You are favored by 3.5")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Back to your team" }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("Full details opens the classic recap", () => {
    render(<SimWeekRecapStory recap={recap} index={0} total={1} ctx={ctx} onNext={() => {}} onClose={() => {}} onFixLineup={() => {}} />);
    const dialog = screen.getByRole("dialog");
    for (let i = 0; i < 4; i += 1) fireEvent.keyDown(dialog, { key: "ArrowRight" });
    fireEvent.click(screen.getByRole("button", { name: "Full details" }));
    expect(screen.getByTestId("week-recap")).toBeInTheDocument();
  });
});
