import { act, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import TradeHistoryPage from "./page";
import { useAuth } from "@/context/AuthContext";
import { api, type PastTradeOutcome } from "@/lib/api";
import { emitTradeOutcomeAnswered } from "@/lib/tradeOutcomeEvents";

vi.mock("@/context/AuthContext", () => ({
  useAuth: vi.fn(),
}));

// A stable router object, like Next's real one: the page's effect depends
// on it, so a fresh object per render would re-run the initial fetch.
const router = { replace: vi.fn(), push: vi.fn() };
vi.mock("next/navigation", () => ({
  useRouter: () => router,
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      getTradeOutcomeHistory: vi.fn(),
    },
  };
});

function past(partner: string): PastTradeOutcome {
  return {
    id: `id-${partner}`,
    league_id: "league-1",
    partner_team_name: partner,
    trade_summary: { partner_team_name: partner, send: [], receive: [], value_edge_label: "" },
    outcome: "yes",
    shared_at: "2026-10-01T00:00:00Z",
    outcome_recorded_at: "2026-10-02T00:00:00Z",
    result_summary: null,
    result_computed_at: null,
  };
}

describe("TradeHistoryPage", () => {
  it("re-fetches when the trade-outcome prompt records an answer", async () => {
    vi.mocked(useAuth).mockReturnValue({
      session: { user: { id: "user-1" } } as never,
      loading: false,
      signIn: vi.fn(),
      signUp: vi.fn(),
      signInWithOAuth: vi.fn(),
      signInAsGuest: vi.fn(),
      signOut: vi.fn(),
      deleteAccount: vi.fn(),
      upgradeGuestWithEmail: vi.fn(),
      callbackNotice: null,
      isGuest: false,
      resetPassword: vi.fn(),
      recoveryPending: false,
      completeRecovery: vi.fn(),
    });
    vi.mocked(api.getTradeOutcomeHistory)
      .mockResolvedValueOnce({ ok: true, outcomes: [past("Team Rocket")] })
      .mockResolvedValueOnce({ ok: true, outcomes: [past("Team Aqua"), past("Team Rocket")] });

    render(<TradeHistoryPage />);
    expect(await screen.findByText("Team Rocket")).toBeInTheDocument();
    expect(screen.queryByText("Team Aqua")).not.toBeInTheDocument();

    await act(async () => {
      emitTradeOutcomeAnswered();
    });

    await waitFor(() => expect(api.getTradeOutcomeHistory).toHaveBeenCalledTimes(2));
    expect(await screen.findByText("Team Aqua")).toBeInTheDocument();
  });
});
