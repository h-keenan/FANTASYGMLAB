import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { OpponentProfileResponse } from "@/lib/opponentProfile";
import { OpponentProfileCard } from "./OpponentProfileCard";

const base: OpponentProfileResponse = {
  ok: true,
  reason: "",
  roster_id: "2",
  direction: { key: "contender", label: "Contender", rank: 2, league_size: 12, record: "5-2", confidence_label: "high" },
  rooms: [
    { position: "RB", rank: 1, of: 12, score: 9000, classification: "covered", tag: "surplus" },
    { position: "WR", rank: 11, of: 12, score: 100, classification: "short_term_need", tag: "need" },
  ],
  strongest: { position: "RB", rank: 1, of: 12 },
  weakest: { position: "WR", rank: 11, of: 12 },
  surplus: ["RB"],
  needs: ["WR"],
  starter_bench: { starter_rank: 2, bench_rank: 9, of: 12, label: "Starter-heavy", note: "Strong starting lineup, thin bench" },
  picks: { rank: 3, of: 12, pick_count: 6, first_rounders: 2, firsts_acquired: 1, firsts_sent: 0 },
  trade_tendency: null,
  trade_angle: {
    text: "You are short at RB and they have RB depth.",
    target: { player_id: "p9", name: "Bench Back", position: "RB", team: "KC", side: "receive" },
  },
};

describe("OpponentProfileCard", () => {
  it("renders reads and an Offer this link prefilled with the target player", () => {
    render(<OpponentProfileCard profile={base} leagueId="L1" leagueName="My League" />);
    expect(screen.getByText("Strongest: RB, 1st of 12")).toBeTruthy();
    expect(screen.getByText("Weakest: WR, 11th of 12")).toBeTruthy();
    expect(screen.getByText(/Starter-heavy/)).toBeTruthy();
    const offer = screen.getByRole("link", { name: "Offer this" });
    expect(offer.getAttribute("href")).toBe("/trade-analyzer/L1?name=My+League&playerId=p9");
  });

  it("hides the Offer button when there is no target player", () => {
    render(
      <OpponentProfileCard profile={{ ...base, trade_angle: { text: "x", target: null } }} leagueId="L1" leagueName="My League" />,
    );
    expect(screen.queryByRole("link", { name: "Offer this" })).toBeNull();
  });

  it("renders nothing for a not-ready profile", () => {
    const { container } = render(
      <OpponentProfileCard profile={{ ok: true, reason: "no_rankings_data", roster_id: "2" }} leagueId="L1" leagueName="x" />,
    );
    expect(container.innerHTML).toBe("");
  });
});
