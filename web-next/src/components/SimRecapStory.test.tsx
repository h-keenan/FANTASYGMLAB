import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { SimWeekRecapStory } from "@/components/SimRecapStory";
import type { SimCtx } from "@/components/SimGameParts";
import type { SimGamePlayer, SimWeekRecap } from "@/lib/simGame";

const player = (id: string, name: string, pos: string) => ({ id, name, pos, team: "KC", age: 25, bye_week: 9, status: "healthy", out_weeks: 0, projection: 12, ros_mean: 12, adp: 20, grade: "B" }) as unknown as SimGamePlayer;
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
  standings: [{ rank: 1, team_id: "1", name: "Goats", is_you: false, wins: 3, losses: 1, ties: 0, pf: 500, pa: 400, rank_delta: 1 }, { rank: 2, team_id: "9", name: "Me", is_you: true, wins: 3, losses: 1, ties: 0, pf: 480, pa: 400, rank_delta: -1 }, { rank: 3, team_id: "2", name: "Brigade", is_you: false, wins: 2, losses: 2, ties: 0, pf: 450, pa: 400, rank_delta: 0 }],
  injuries: [],
  season_complete: false,
  champion: null,
  next_week: 5,
} as unknown as SimWeekRecap;
const openPlayer = vi.fn();
const ctx = {
  game: { status: "in_season", week: 5, settings: { mode: "redraft", playoff_teams: 2 }, you: { team_id: "9", name: "Me" }, trade_deadline_week: 10, pending: { lineup_warnings: 1, inbox: 2 }, this_week: { opponent: { team_id: "3", name: "Titans" }, bye: false, your_projection: 121.4, opponent_projection: 117.9 } },
  openPlayer,
} as unknown as SimCtx;

describe("SimWeekRecapStory", () => {
  it("shows Result, Matchup, Injuries, League, Next as story pages with a Fix lineup action and a final CTA", () => {
    const onClose = vi.fn();
    const onFix = vi.fn();
    render(<SimWeekRecapStory recap={recap} index={0} total={1} ctx={ctx} onNext={() => {}} onClose={onClose} onFixLineup={onFix} />);
    const labels = screen.getAllByRole("button", { name: /^Go to / }).map((b) => b.getAttribute("aria-label"));
    expect(labels).toHaveLength(6);
    expect(screen.getByTestId("story-title")).toHaveTextContent("Matchup Result");
    expect(screen.getByText("Won by 18.7")).toBeInTheDocument();
    const dialog = screen.getByRole("dialog");
    fireEvent.keyDown(dialog, { key: "ArrowRight" });
    expect(screen.getByText("96%")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Quinn Moore.*show details/ }));
    fireEvent.click(screen.getByRole("button", { name: "Open profile" }));
    expect(openPlayer).toHaveBeenCalledTimes(1);
    fireEvent.keyDown(dialog, { key: "ArrowRight" });
    fireEvent.click(screen.getByRole("button", { name: "Fix lineup" }));
    expect(onFix).toHaveBeenCalledTimes(1);
    fireEvent.keyDown(dialog, { key: "ArrowRight" });
    expect(screen.getByText("Top score: Goats")).toBeInTheDocument();
    fireEvent.keyDown(dialog, { key: "ArrowRight" });
    expect(screen.getByTestId("story-title")).toHaveTextContent("Standings");
    expect(screen.getAllByTestId("recap-standing-row")).toHaveLength(3);
    expect(screen.getByText("Seed 2, down 1")).toBeInTheDocument();
    fireEvent.keyDown(dialog, { key: "ArrowRight" });
    expect(screen.getByText("Titans")).toBeInTheDocument();
    expect(screen.getByText("You are favored by 3.5")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Back to your team" }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("result page: sim team logos (never initials circles), names uncut, and no blank Grade chip when a player has no grade", () => {
    const noGrade = { ...recap, your_game: { ...recap.your_game!, starters: [{ slot: "QB", player: { ...player("q", "Quinn Moore", "QB"), grade: null }, pts: 25, flag: null }] } } as unknown as SimWeekRecap;
    render(<SimWeekRecapStory recap={noGrade} index={0} total={1} ctx={ctx} onNext={() => {}} onClose={() => {}} onFixLineup={() => {}} />);
    expect(screen.getAllByTestId("sim-crest").length).toBeGreaterThanOrEqual(2);
    expect(screen.getAllByTestId("sim-team-identity").length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText("Grade")).not.toBeInTheDocument();
  });

  it("Full details opens the classic recap", () => {
    render(<SimWeekRecapStory recap={recap} index={0} total={1} ctx={ctx} onNext={() => {}} onClose={() => {}} onFixLineup={() => {}} />);
    const dialog = screen.getByRole("dialog");
    for (let i = 0; i < 5; i += 1) fireEvent.keyDown(dialog, { key: "ArrowRight" });
    fireEvent.click(screen.getByRole("button", { name: "Full details" }));
    expect(screen.getByTestId("week-recap")).toBeInTheDocument();
  });

  const final = (over: Record<string, unknown>) =>
    ({
      ...recap,
      kind: "playoff",
      round: 3,
      season_complete: true,
      next_week: null,
      standings: [{ rank: 1, team_id: "9", name: "Me", is_you: true, wins: 11, losses: 3, ties: 0, pf: 1800, pa: 1500 }, { rank: 2, team_id: "7", name: "Rats", is_you: false, wins: 10, losses: 4, ties: 0, pf: 1700, pa: 1500 }],
      ...over,
    }) as unknown as SimWeekRecap;

  it("championship win: trophy, 'Champions' headline, confetti, glow, then the season page", () => {
    render(<SimWeekRecapStory recap={final({ champion: "9" })} index={0} total={1} ctx={ctx} onNext={() => {}} onClose={() => {}} onFixLineup={() => {}} />);
    expect(screen.getByTestId("recap-headline")).toHaveTextContent("Champions");
    expect(screen.getByTestId("recap-trophy")).toBeInTheDocument();
    expect(screen.getByTestId("confetti")).toBeInTheDocument();
    expect(screen.getByTestId("recap-glow")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /^Go to / }).at(-1)).toHaveAttribute("aria-label", expect.stringContaining("Season complete"));
  });

  it("a lost playoff game is Eliminated with the trophy but no confetti; a regular win has neither", () => {
    const lost = { ...recap.your_game, result: "loss", your_pts: 90, opp_pts: 100 };
    const { unmount } = render(<SimWeekRecapStory recap={{ ...recap, kind: "playoff", round: 1, your_game: lost } as unknown as SimWeekRecap} index={0} total={2} ctx={ctx} onNext={() => {}} onClose={() => {}} onFixLineup={() => {}} />);
    expect(screen.getByTestId("recap-headline")).toHaveTextContent("Eliminated");
    expect(screen.getByTestId("recap-trophy")).toBeInTheDocument();
    expect(screen.queryByTestId("confetti")).not.toBeInTheDocument();
    unmount();
    render(<SimWeekRecapStory recap={recap} index={0} total={1} ctx={ctx} onNext={() => {}} onClose={() => {}} onFixLineup={() => {}} />);
    expect(screen.getByTestId("recap-headline")).toHaveTextContent("Win");
    expect(screen.queryByTestId("recap-trophy")).not.toBeInTheDocument();
    expect(screen.queryByTestId("confetti")).not.toBeInTheDocument();
  });

  it("injuries show one marker per player: the OUT chip plus a duration, never 'Out 4w' as well", () => {
    const hurt = { ...recap, injuries: [{ player: player("a", "Alf Hurt", "WR"), weeks: 4, team_id: "9", is_yours: true }] } as unknown as SimWeekRecap;
    render(<SimWeekRecapStory recap={hurt} index={0} total={1} ctx={ctx} onNext={() => {}} onClose={() => {}} onFixLineup={() => {}} />);
    const dialog = screen.getByRole("dialog");
    fireEvent.keyDown(dialog, { key: "ArrowRight" });
    fireEvent.keyDown(dialog, { key: "ArrowRight" });
    expect(screen.getByText("4 weeks · yours")).toBeInTheDocument();
    expect(screen.queryByText(/Out 4w/)).not.toBeInTheDocument();
  });
});
