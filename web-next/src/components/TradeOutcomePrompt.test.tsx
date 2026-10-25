import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { TradeOutcomePrompt } from "./TradeOutcomePrompt";
import { useAuth } from "@/context/AuthContext";
import { api, type PendingTradeOutcome } from "@/lib/api";
import { onTradeOutcomeAnswered } from "@/lib/tradeOutcomeEvents";

vi.mock("@/context/AuthContext", () => ({
  useAuth: vi.fn(),
}));

let mockPathname = "/dashboard/league-1";
vi.mock("next/navigation", () => ({
  usePathname: () => mockPathname,
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      getPendingTradeOutcomes: vi.fn(),
      answerTradeOutcome: vi.fn(),
    },
  };
});

function mockAuth(signedIn: boolean) {
  vi.mocked(useAuth).mockReturnValue({
    session: (signedIn ? { user: { id: "user-1" } } : null) as never,
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
  });
}

function outcome(id: string, partner: string): PendingTradeOutcome {
  return {
    id,
    league_id: "league-1",
    partner_team_name: partner,
    shared_at: "2026-10-01T00:00:00Z",
    trade_summary: {
      partner_team_name: partner,
      send: [{ name: "Bijan Robinson", position: "RB" }],
      receive: [{ name: "Ja'Marr Chase", position: "WR" }],
      value_edge_label: "+120",
    },
  };
}

beforeEach(() => {
  mockPathname = "/dashboard/league-1";
  window.sessionStorage.clear();
  vi.mocked(api.getPendingTradeOutcomes).mockReset();
  vi.mocked(api.answerTradeOutcome).mockReset();
  vi.mocked(api.answerTradeOutcome).mockResolvedValue({ ok: true, reason: "" });
});

afterEach(() => {
  vi.mocked(useAuth).mockReset();
});

describe("TradeOutcomePrompt", () => {
  it("shows the oldest pending outcome with mobile's copy", async () => {
    mockAuth(true);
    vi.mocked(api.getPendingTradeOutcomes).mockResolvedValue({
      ok: true,
      outcomes: [outcome("o-1", "Team Rocket"), outcome("o-2", "Team Aqua")],
    });

    render(<TradeOutcomePrompt />);

    expect(await screen.findByText("Did this trade happen?")).toBeInTheDocument();
    expect(screen.getByText("You shared a trade with Team Rocket")).toBeInTheDocument();
    expect(screen.getByText("Bijan Robinson")).toBeInTheDocument();
    expect(screen.getByText("Ja'Marr Chase")).toBeInTheDocument();
    for (const label of ["Yes, it happened", "No", "Still pending", "Didn't send"]) {
      expect(screen.getByRole("button", { name: label })).toBeInTheDocument();
    }
    // One at a time: the second pending trade isn't rendered yet.
    expect(screen.queryByText("You shared a trade with Team Aqua")).not.toBeInTheDocument();
  });

  it.each([
    ["Yes, it happened", "yes"],
    ["No", "no"],
    ["Still pending", "still_pending"],
    ["Didn't send", "didnt_send"],
  ] as const)("answering %s calls the endpoint and hides it", async (label, value) => {
    mockAuth(true);
    vi.mocked(api.getPendingTradeOutcomes).mockResolvedValue({ ok: true, outcomes: [outcome("o-1", "Team Rocket")] });

    render(<TradeOutcomePrompt />);
    fireEvent.click(await screen.findByRole("button", { name: label }));

    await waitFor(() => expect(api.answerTradeOutcome).toHaveBeenCalledWith("o-1", value));
    await waitFor(() => expect(screen.queryByTestId("trade-outcome-prompt")).not.toBeInTheDocument());
  });

  it.each([
    ["Yes, it happened", 1],
    ["Still pending", 0],
  ] as const)("answering %s tells an open Trade History page to refresh (%i times)", async (label, expected) => {
    mockAuth(true);
    vi.mocked(api.getPendingTradeOutcomes).mockResolvedValue({ ok: true, outcomes: [outcome("o-1", "Team Rocket")] });
    const listener = vi.fn();
    const unsubscribe = onTradeOutcomeAnswered(listener);

    render(<TradeOutcomePrompt />);
    fireEvent.click(await screen.findByRole("button", { name: label }));
    await waitFor(() => expect(screen.queryByTestId("trade-outcome-prompt")).not.toBeInTheDocument());

    expect(listener).toHaveBeenCalledTimes(expected);
    unsubscribe();
  });

  it("moves to the next pending outcome after an answer", async () => {
    mockAuth(true);
    vi.mocked(api.getPendingTradeOutcomes).mockResolvedValue({
      ok: true,
      outcomes: [outcome("o-1", "Team Rocket"), outcome("o-2", "Team Aqua")],
    });

    render(<TradeOutcomePrompt />);
    fireEvent.click(await screen.findByRole("button", { name: "Yes, it happened" }));

    expect(await screen.findByText("You shared a trade with Team Aqua")).toBeInTheDocument();
  });

  it("keeps the outcome when the answer request fails", async () => {
    mockAuth(true);
    vi.mocked(api.getPendingTradeOutcomes).mockResolvedValue({ ok: true, outcomes: [outcome("o-1", "Team Rocket")] });
    vi.mocked(api.answerTradeOutcome).mockRejectedValue(new Error("offline"));

    render(<TradeOutcomePrompt />);
    fireEvent.click(await screen.findByRole("button", { name: "No" }));

    await waitFor(() => expect(api.answerTradeOutcome).toHaveBeenCalled());
    expect(screen.getByTestId("trade-outcome-prompt")).toBeInTheDocument();
  });

  it("dismissing hides it for the rest of the session without answering", async () => {
    mockAuth(true);
    vi.mocked(api.getPendingTradeOutcomes).mockResolvedValue({
      ok: true,
      outcomes: [outcome("o-1", "Team Rocket"), outcome("o-2", "Team Aqua")],
    });

    const { unmount } = render(<TradeOutcomePrompt />);
    fireEvent.click(await screen.findByRole("button", { name: "Dismiss trade follow-up" }));

    expect(screen.queryByTestId("trade-outcome-prompt")).not.toBeInTheDocument();
    expect(api.answerTradeOutcome).not.toHaveBeenCalled();

    // Returning to the tab doesn't bring it back or even re-fetch.
    vi.mocked(api.getPendingTradeOutcomes).mockClear();
    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
    });
    expect(api.getPendingTradeOutcomes).not.toHaveBeenCalled();

    // A fresh mount in the same browser session stays hidden too.
    unmount();
    render(<TradeOutcomePrompt />);
    await act(async () => {});
    expect(screen.queryByTestId("trade-outcome-prompt")).not.toBeInTheDocument();
    expect(api.getPendingTradeOutcomes).not.toHaveBeenCalled();
  });

  it("re-checks pending outcomes when the tab becomes visible", async () => {
    mockAuth(true);
    vi.mocked(api.getPendingTradeOutcomes).mockResolvedValueOnce({ ok: true, outcomes: [] });

    render(<TradeOutcomePrompt />);
    await waitFor(() => expect(api.getPendingTradeOutcomes).toHaveBeenCalledTimes(1));
    expect(screen.queryByTestId("trade-outcome-prompt")).not.toBeInTheDocument();

    vi.mocked(api.getPendingTradeOutcomes).mockResolvedValueOnce({ ok: true, outcomes: [outcome("o-1", "Team Rocket")] });
    await act(async () => {
      document.dispatchEvent(new Event("visibilitychange"));
    });

    expect(await screen.findByTestId("trade-outcome-prompt")).toBeInTheDocument();
  });

  it("shows nothing and never calls the API when logged out", async () => {
    mockAuth(false);

    render(<TradeOutcomePrompt />);
    await act(async () => {});

    expect(screen.queryByTestId("trade-outcome-prompt")).not.toBeInTheDocument();
    expect(api.getPendingTradeOutcomes).not.toHaveBeenCalled();
  });

  it("shows nothing when there are no pending outcomes", async () => {
    mockAuth(true);
    vi.mocked(api.getPendingTradeOutcomes).mockResolvedValue({ ok: true, outcomes: [] });

    render(<TradeOutcomePrompt />);
    await waitFor(() => expect(api.getPendingTradeOutcomes).toHaveBeenCalled());

    expect(screen.queryByTestId("trade-outcome-prompt")).not.toBeInTheDocument();
  });

  it("shows nothing when the pending check fails", async () => {
    mockAuth(true);
    vi.mocked(api.getPendingTradeOutcomes).mockRejectedValue(new Error("offline"));

    render(<TradeOutcomePrompt />);
    await waitFor(() => expect(api.getPendingTradeOutcomes).toHaveBeenCalled());

    expect(screen.queryByTestId("trade-outcome-prompt")).not.toBeInTheDocument();
  });

  it.each(["/", "/premium"])("stays hidden on the onboarding/paywall route %s", async (path) => {
    mockPathname = path;
    mockAuth(true);
    vi.mocked(api.getPendingTradeOutcomes).mockResolvedValue({ ok: true, outcomes: [outcome("o-1", "Team Rocket")] });

    render(<TradeOutcomePrompt />);
    await waitFor(() => expect(api.getPendingTradeOutcomes).toHaveBeenCalled());

    expect(screen.queryByTestId("trade-outcome-prompt")).not.toBeInTheDocument();
  });
});
