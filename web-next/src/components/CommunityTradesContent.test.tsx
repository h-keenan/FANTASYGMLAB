import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { CommunityTradesContent } from "./CommunityTradesContent";
import type { CommunityTradeItem } from "@/lib/api";

const REACTION_EMOJI = ["\u{1F525}", "\u{1F62D}", "\u{1F480}"];

function item(overrides: Partial<CommunityTradeItem>): CommunityTradeItem {
  return {
    id: "outcome-1",
    send: [{ name: "Sender Guy", position: "WR", player_id: "100", value_score: 70 }],
    receive: [{ name: "Receiver Guy", position: "RB", player_id: "200", value_score: 90 }],
    verdict: "worked_out",
    verdict_label: "This trade has worked out",
    confidence: "high",
    production: { net_points_ppr: 30, avg_net_per_week: 6.2, weeks_counted: 5 },
    value: { sent_delta_pct: -4, received_delta_pct: 16, net_delta_pct: 20 },
    occurred_at: "2026-09-01T00:00:00Z",
    reactions: {},
    my_reactions: [],
    ...overrides,
  };
}

describe("CommunityTradesContent", () => {
  it("shows the no-trades empty state", () => {
    render(
      <CommunityTradesContent
        trades={[]}
        reactionEmoji={REACTION_EMOJI}
        optedOut={false}
        onReact={vi.fn()}
        onToggleOptOut={vi.fn()}
      />,
    );

    expect(screen.getByText(/No standout trades yet/)).toBeInTheDocument();
  });

  it("renders a trade anonymized as Team A / Team B with its assets and verdict", () => {
    render(
      <CommunityTradesContent
        trades={[item({})]}
        reactionEmoji={REACTION_EMOJI}
        optedOut={false}
        onReact={vi.fn()}
        onToggleOptOut={vi.fn()}
      />,
    );

    expect(screen.getByText("Team A traded with Team B")).toBeInTheDocument();
    expect(screen.getByText("Sender Guy")).toBeInTheDocument();
    expect(screen.getByText("Receiver Guy")).toBeInTheDocument();
    expect(screen.getByText("This trade has worked out")).toBeInTheDocument();
    expect(screen.getByText("+6.2 PPR pts/wk edge since the trade · +20% value trend edge")).toBeInTheDocument();
  });

  it("never renders any real team/user identity field", () => {
    render(
      <CommunityTradesContent
        trades={[item({})]}
        reactionEmoji={REACTION_EMOJI}
        optedOut={false}
        onReact={vi.fn()}
        onToggleOptOut={vi.fn()}
      />,
    );

    expect(screen.queryByText(/partner/i)).not.toBeInTheDocument();
  });

  it("renders every reaction emoji with its count and calls onReact when tapped", () => {
    const onReact = vi.fn();
    render(
      <CommunityTradesContent
        trades={[item({ reactions: { "\u{1F525}": 3 }, my_reactions: ["\u{1F525}"] })]}
        reactionEmoji={REACTION_EMOJI}
        optedOut={false}
        onReact={onReact}
        onToggleOptOut={vi.fn()}
      />,
    );

    const fireButton = screen.getByRole("button", { name: /\u{1F525}/u });
    expect(fireButton).toHaveTextContent("3");
    expect(fireButton).toHaveAttribute("aria-pressed", "true");

    fireEvent.click(fireButton);
    expect(onReact).toHaveBeenCalledWith("outcome-1", "\u{1F525}", true);
  });

  it("shows an unreacted emoji with no count and calls onReact with active=false", () => {
    const onReact = vi.fn();
    render(
      <CommunityTradesContent
        trades={[item({})]}
        reactionEmoji={REACTION_EMOJI}
        optedOut={false}
        onReact={onReact}
        onToggleOptOut={vi.fn()}
      />,
    );

    const skullButton = screen.getByRole("button", { name: /\u{1F480}/u });
    expect(skullButton).toHaveAttribute("aria-pressed", "false");
    fireEvent.click(skullButton);
    expect(onReact).toHaveBeenCalledWith("outcome-1", "\u{1F480}", false);
  });

  it("shows the opt-out toggle and calls onToggleOptOut with the flipped value", () => {
    const onToggleOptOut = vi.fn();
    render(
      <CommunityTradesContent
        trades={[]}
        reactionEmoji={REACTION_EMOJI}
        optedOut={false}
        onReact={vi.fn()}
        onToggleOptOut={onToggleOptOut}
      />,
    );

    expect(screen.getByText("I don't want MY trades to appear in this feed")).toBeInTheDocument();
    const toggle = screen.getByRole("switch");
    expect(toggle).toHaveAttribute("aria-checked", "false");
    expect(toggle).toHaveTextContent("Opted in");

    fireEvent.click(toggle);
    expect(onToggleOptOut).toHaveBeenCalledWith(true);
  });

  it("reflects an already-opted-out state", () => {
    render(
      <CommunityTradesContent
        trades={[]}
        reactionEmoji={REACTION_EMOJI}
        optedOut={true}
        onReact={vi.fn()}
        onToggleOptOut={vi.fn()}
      />,
    );

    const toggle = screen.getByRole("switch");
    expect(toggle).toHaveAttribute("aria-checked", "true");
    expect(toggle).toHaveTextContent("Opted out");
  });
});
