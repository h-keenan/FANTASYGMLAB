import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { TradeHistoryContent } from "./TradeHistoryContent";
import type { PastTradeOutcome, TradeOutcomeHistoryResponse } from "@/lib/api";

function outcome(overrides: Partial<PastTradeOutcome>): PastTradeOutcome {
  return {
    id: "outcome-1",
    league_id: "league-1",
    partner_team_name: "The Gridiron Gurus",
    trade_summary: {
      partner_team_name: "The Gridiron Gurus",
      send: [{ name: "Test Sender", position: "WR", player_id: "100", value_score: 80 }],
      receive: [{ name: "Test Receiver", position: "RB", player_id: "200", value_score: 90 }],
      value_edge_label: "",
      valuation_lens: "Dynasty",
    },
    outcome: "yes",
    shared_at: "2026-08-01T00:00:00Z",
    outcome_recorded_at: "2026-08-02T00:00:00Z",
    result_summary: null,
    result_computed_at: null,
    ...overrides,
  };
}

describe("TradeHistoryContent", () => {
  it("shows the no-history empty state", () => {
    const data: TradeOutcomeHistoryResponse = { ok: true, outcomes: [] };
    render(<TradeHistoryContent data={data} />);

    expect(screen.getByText("No trade history yet. Confirm a trade to see it here.")).toBeInTheDocument();
  });

  it("renders a confirmed trade's partner, date, and send/receive assets", () => {
    const data: TradeOutcomeHistoryResponse = { ok: true, outcomes: [outcome({})] };
    render(<TradeHistoryContent data={data} />);

    expect(screen.getByText("The Gridiron Gurus")).toBeInTheDocument();
    expect(screen.getByText("Made it")).toBeInTheDocument();
    expect(screen.getByText("Test Sender")).toBeInTheDocument();
    expect(screen.getByText("Test Receiver")).toBeInTheDocument();
  });

  it("shows no verdict section for a confirmed trade with no computed result yet", () => {
    render(<TradeHistoryContent data={{ ok: true, outcomes: [outcome({ result_summary: null })] }} />);

    expect(screen.queryByText(/edge since the trade/)).not.toBeInTheDocument();
  });

  it("shows no verdict section when the result is only insufficient_data", () => {
    render(
      <TradeHistoryContent
        data={{
          ok: true,
          outcomes: [
            outcome({
              result_summary: {
                status: "insufficient_data",
                reason: "no_stat_data_yet",
                verdict: null,
                days_since_trade: 30,
              },
            }),
          ],
        }}
      />,
    );

    expect(screen.queryByText(/edge since the trade/)).not.toBeInTheDocument();
  });

  it("renders a ready verdict's label and detail text", () => {
    render(
      <TradeHistoryContent
        data={{
          ok: true,
          outcomes: [
            outcome({
              result_summary: {
                status: "ready",
                reason: "",
                verdict: "worked_out",
                verdict_label: "This trade has worked out",
                confidence: "high",
                days_since_trade: 35,
                production: { net_points_ppr: 21, avg_net_per_week: 4.2, weeks_counted: 5 },
                value: { sent_delta_pct: -2, received_delta_pct: 10, net_delta_pct: 12 },
              },
            }),
          ],
        }}
      />,
    );

    expect(screen.getByText("This trade has worked out")).toBeInTheDocument();
    expect(screen.getByText("+4.2 PPR pts/wk edge since the trade · +12% value trend edge")).toBeInTheDocument();
  });

  it("never shows a verdict for a trade the user said they didn't make, even with a result_summary present", () => {
    render(
      <TradeHistoryContent
        data={{
          ok: true,
          outcomes: [
            outcome({
              outcome: "no",
              result_summary: {
                status: "ready",
                reason: "",
                verdict: "worked_out",
                verdict_label: "This trade has worked out",
                confidence: "high",
                days_since_trade: 35,
              },
            }),
          ],
        }}
      />,
    );

    expect(screen.getByText("Didn't make it")).toBeInTheDocument();
    expect(screen.queryByText("This trade has worked out")).not.toBeInTheDocument();
  });
});
