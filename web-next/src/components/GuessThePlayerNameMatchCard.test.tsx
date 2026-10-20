import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { GuessThePlayerNameMatchCard } from "./GuessThePlayerNameMatchCard";
import {
  api,
  type GuessThePlayerNameMatchAnswerResponse,
  type GuessThePlayerNameMatchResponse,
} from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      getGuessThePlayerNameMatch: vi.fn(),
      answerGuessThePlayerNameMatch: vi.fn(),
    },
  };
});

function promptResponse(overrides: Partial<GuessThePlayerNameMatchResponse> = {}): GuessThePlayerNameMatchResponse {
  return {
    ok: true,
    available: true,
    reason: "",
    already_answered: false,
    last_result: null,
    correct_pairing: null,
    streak: { current_streak: 1, best_streak: 4 },
    prompt: {
      pick_id: "pair-1",
      season: 2025,
      week: 5,
      famous_player: { player_id: "4", name: "Star RB", team: "SF", position: "RB", tier: "elite" },
      obscure_player: { player_id: "1", name: "Bench Runner", team: "KC", position: "RB", tier: "depth" },
      slots: {
        A: { stat_line: [{ label: "Rush Attempts", value: 14 }], fantasy_points_ppr: 21 },
        B: { stat_line: [{ label: "Rush Attempts", value: 22 }], fantasy_points_ppr: 30 },
      },
    },
    ...overrides,
  };
}

function answerResponse(
  overrides: Partial<GuessThePlayerNameMatchAnswerResponse> = {},
): GuessThePlayerNameMatchAnswerResponse {
  return {
    ok: true,
    already_answered: false,
    correct: true,
    correct_pairing: { famous_slot: "A", obscure_slot: "B" },
    streak: { current_streak: 2, best_streak: 4 },
    ...overrides,
  };
}

beforeEach(() => {
  vi.mocked(api.getGuessThePlayerNameMatch).mockReset();
  vi.mocked(api.answerGuessThePlayerNameMatch).mockReset();
  // The dismiss-persistence fix writes a real key to window.localStorage,
  // which otherwise survives across tests in this same file/worker.
  window.localStorage.clear();
});

describe("GuessThePlayerNameMatchCard", () => {
  it("renders nothing while loading and nothing on fetch failure", async () => {
    vi.mocked(api.getGuessThePlayerNameMatch).mockRejectedValue(new Error("down"));
    const { container } = render(<GuessThePlayerNameMatchCard />);
    expect(container).toBeEmptyDOMElement();
    await waitFor(() => expect(api.getGuessThePlayerNameMatch).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when the backend reports no pairing today", async () => {
    vi.mocked(api.getGuessThePlayerNameMatch).mockResolvedValue(
      promptResponse({ available: false, prompt: null, reason: "no_name_match_pairing_today" }),
    );
    const { container } = render(<GuessThePlayerNameMatchCard />);
    await waitFor(() => expect(api.getGuessThePlayerNameMatch).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it("shows BOTH real identities up front, and the real stat lines unlabeled", async () => {
    vi.mocked(api.getGuessThePlayerNameMatch).mockResolvedValue(promptResponse());
    render(<GuessThePlayerNameMatchCard />);

    await screen.findByText("Who Is Who?");
    // "Star RB" also appears inside the "Which stat line belongs to..."
    // prompt copy below, so both players' names are checked for
    // at-least-one real appearance rather than exactly one.
    expect(screen.getAllByText("Star RB").length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText("Bench Runner").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Stat Line A")).toBeInTheDocument();
    expect(screen.getByText("Stat Line B")).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /Stat Line A/ })).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: /Stat Line B/ })).toBeInTheDocument();
  });

  it("submits a guess, reveals the real pairing, and updates this game's own streak", async () => {
    vi.mocked(api.getGuessThePlayerNameMatch).mockResolvedValue(promptResponse());
    vi.mocked(api.answerGuessThePlayerNameMatch).mockResolvedValue(answerResponse());
    render(<GuessThePlayerNameMatchCard />);

    const slotA = await screen.findByRole("radio", { name: /Stat Line A/ });
    fireEvent.click(slotA);

    await waitFor(() => expect(screen.getByText("Correct!", { exact: false })).toBeInTheDocument());
    expect(api.answerGuessThePlayerNameMatch).toHaveBeenCalledWith("pair-1", "A");
    expect(screen.getByText(/2 in a row/)).toBeInTheDocument();
  });

  it("shows the wrong-answer message on an incorrect guess", async () => {
    vi.mocked(api.getGuessThePlayerNameMatch).mockResolvedValue(promptResponse());
    vi.mocked(api.answerGuessThePlayerNameMatch).mockResolvedValue(
      answerResponse({ correct: false, streak: { current_streak: 0, best_streak: 4 } }),
    );
    render(<GuessThePlayerNameMatchCard />);

    const slotB = await screen.findByRole("radio", { name: /Stat Line B/ });
    fireEvent.click(slotB);

    await waitFor(() => expect(screen.getByText("Not quite.", { exact: false })).toBeInTheDocument());
    expect(api.answerGuessThePlayerNameMatch).toHaveBeenCalledWith("pair-1", "B");
  });

  it("renders the already-revealed state on load when the user already answered today", async () => {
    vi.mocked(api.getGuessThePlayerNameMatch).mockResolvedValue(
      promptResponse({
        already_answered: true,
        last_result: "correct",
        correct_pairing: { famous_slot: "A", obscure_slot: "B" },
      }),
    );
    render(<GuessThePlayerNameMatchCard />);

    await screen.findByText("Correct!", { exact: false });
    expect(api.answerGuessThePlayerNameMatch).not.toHaveBeenCalled();
  });

  it("is dismissible via the close button", async () => {
    vi.mocked(api.getGuessThePlayerNameMatch).mockResolvedValue(promptResponse());
    const { container } = render(<GuessThePlayerNameMatchCard />);

    await screen.findByText("Who Is Who?");
    fireEvent.click(screen.getByLabelText("Dismiss Name Match"));

    expect(container).toBeEmptyDOMElement();
  });

  // Same real bug GuessThePlayerCard.tsx had to be retrofitted for
  // (coridian_: "if you exit that module out, it shouldn't pop back up")
  // — built correctly here from the start, but still covered by the exact
  // same remount repro so it can never silently regress.
  it("stays dismissed across a fresh remount for the same day's pick", async () => {
    vi.mocked(api.getGuessThePlayerNameMatch).mockResolvedValue(promptResponse());
    const first = render(<GuessThePlayerNameMatchCard />);
    await screen.findByText("Who Is Who?");
    fireEvent.click(screen.getByLabelText("Dismiss Name Match"));
    expect(first.container).toBeEmptyDOMElement();
    first.unmount();

    vi.mocked(api.getGuessThePlayerNameMatch).mockResolvedValue(promptResponse());
    const second = render(<GuessThePlayerNameMatchCard />);
    await waitFor(() => expect(api.getGuessThePlayerNameMatch).toHaveBeenCalledTimes(2));
    expect(second.container).toBeEmptyDOMElement();
  });

  it("shows again for a NEW day's different pick_id despite a stale dismiss", async () => {
    vi.mocked(api.getGuessThePlayerNameMatch).mockResolvedValue(promptResponse());
    const first = render(<GuessThePlayerNameMatchCard />);
    await screen.findByText("Who Is Who?");
    fireEvent.click(screen.getByLabelText("Dismiss Name Match"));
    first.unmount();

    const dayTwo = promptResponse();
    dayTwo.prompt!.pick_id = "pair-2";
    vi.mocked(api.getGuessThePlayerNameMatch).mockResolvedValue(dayTwo);
    render(<GuessThePlayerNameMatchCard />);
    await screen.findByText("Who Is Who?");
  });

  it("disables slots once answered so a second click cannot double-submit", async () => {
    vi.mocked(api.getGuessThePlayerNameMatch).mockResolvedValue(promptResponse());
    vi.mocked(api.answerGuessThePlayerNameMatch).mockResolvedValue(answerResponse());
    render(<GuessThePlayerNameMatchCard />);

    const slotA = await screen.findByRole("radio", { name: /Stat Line A/ });
    fireEvent.click(slotA);
    await waitFor(() => expect(screen.getByText("Correct!", { exact: false })).toBeInTheDocument());

    expect(screen.getByRole("radio", { name: /Stat Line A/ })).toBeDisabled();
    expect(screen.getByRole("radio", { name: /Stat Line B/ })).toBeDisabled();
    expect(api.answerGuessThePlayerNameMatch).toHaveBeenCalledTimes(1);
  });

  it("uses a storage key distinct from GuessThePlayerCard's own dismiss key", async () => {
    vi.mocked(api.getGuessThePlayerNameMatch).mockResolvedValue(promptResponse());
    render(<GuessThePlayerNameMatchCard />);
    await screen.findByText("Who Is Who?");
    fireEvent.click(screen.getByLabelText("Dismiss Name Match"));

    expect(window.localStorage.getItem("fd:guess-the-player-name-match-dismissed-pick-id")).toBe("pair-1");
    expect(window.localStorage.getItem("fd:guess-the-player-dismissed-pick-id")).toBeNull();
  });
});
