import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { GuessThePlayerCard } from "./GuessThePlayerCard";
import { api, type GuessThePlayerAnswerResponse, type GuessThePlayerResponse } from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      getGuessThePlayer: vi.fn(),
      answerGuessThePlayer: vi.fn(),
    },
  };
});

function promptResponse(overrides: Partial<GuessThePlayerResponse> = {}): GuessThePlayerResponse {
  return {
    ok: true,
    available: true,
    reason: "",
    already_answered: false,
    last_result: null,
    correct_player: null,
    streak: { current_streak: 2, best_streak: 5 },
    prompt: {
      pick_id: "pick-1",
      season: 2025,
      week: 5,
      position: "RB",
      tier: "depth",
      stat_line: [{ label: "Rush Attempts", value: 22 }],
      fantasy_points_ppr: 30,
      options: [
        { player_id: "1", name: "Bench Runner" },
        { player_id: "2", name: "Other Back" },
        { player_id: "3", name: "Third Back" },
        { player_id: "4", name: "Fourth Back" },
      ],
    },
    ...overrides,
  };
}

function answerResponse(overrides: Partial<GuessThePlayerAnswerResponse> = {}): GuessThePlayerAnswerResponse {
  return {
    ok: true,
    already_answered: false,
    correct: true,
    correct_player: { player_id: "1", name: "Bench Runner", team: "KC", position: "RB", tier: "depth" },
    streak: { current_streak: 3, best_streak: 5 },
    ...overrides,
  };
}

beforeEach(() => {
  vi.mocked(api.getGuessThePlayer).mockReset();
  vi.mocked(api.answerGuessThePlayer).mockReset();
  // The dismiss-persistence fix writes a real key to window.localStorage,
  // which otherwise survives across tests in this same file/worker.
  window.localStorage.clear();
});

describe("GuessThePlayerCard", () => {
  it("renders nothing while loading and nothing on fetch failure", async () => {
    vi.mocked(api.getGuessThePlayer).mockRejectedValue(new Error("down"));
    const { container } = render(<GuessThePlayerCard />);
    expect(container).toBeEmptyDOMElement();
    await waitFor(() => expect(api.getGuessThePlayer).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when the backend reports no surprising pick today", async () => {
    vi.mocked(api.getGuessThePlayer).mockResolvedValue(
      promptResponse({ available: false, prompt: null, reason: "no_surprising_player_today" }),
    );
    const { container } = render(<GuessThePlayerCard />);
    await waitFor(() => expect(api.getGuessThePlayer).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it("hides the real name/team before a guess, shows the real stat line and options", async () => {
    vi.mocked(api.getGuessThePlayer).mockResolvedValue(promptResponse());
    render(<GuessThePlayerCard />);

    await screen.findByText("Whose stats are these?");
    expect(screen.getByText("??? ???")).toBeInTheDocument();
    // The real player's name IS one of the four options (indistinguishable
    // from the distractors) — only the identity header must stay hidden.
    expect(screen.getAllByText("Bench Runner")).toHaveLength(1);
    expect(screen.getByText("22")).toBeInTheDocument();
    expect(screen.getByText("Rush Attempts")).toBeInTheDocument();
    expect(screen.getByRole("radio", { name: "Other Back" })).toBeInTheDocument();
  });

  it("submits a guess, reveals the real identity, and updates the streak", async () => {
    vi.mocked(api.getGuessThePlayer).mockResolvedValue(promptResponse());
    vi.mocked(api.answerGuessThePlayer).mockResolvedValue(answerResponse());
    render(<GuessThePlayerCard />);

    const option = await screen.findByRole("radio", { name: "Bench Runner" });
    fireEvent.click(option);

    await waitFor(() => expect(screen.getByText("Correct!")).toBeInTheDocument());
    expect(api.answerGuessThePlayer).toHaveBeenCalledWith("pick-1", "1");
    expect(screen.getAllByText("Bench Runner").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("KC")).toBeInTheDocument();
    expect(screen.getByText(/3 in a row/)).toBeInTheDocument();
  });

  it("shows the wrong-answer message and the real correct player on an incorrect guess", async () => {
    vi.mocked(api.getGuessThePlayer).mockResolvedValue(promptResponse());
    vi.mocked(api.answerGuessThePlayer).mockResolvedValue(
      answerResponse({ correct: false, streak: { current_streak: 0, best_streak: 5 } }),
    );
    render(<GuessThePlayerCard />);

    const option = await screen.findByRole("radio", { name: "Other Back" });
    fireEvent.click(option);

    await waitFor(() => expect(screen.getByText("Not quite — it was Bench Runner.")).toBeInTheDocument());
    expect(api.answerGuessThePlayer).toHaveBeenCalledWith("pick-1", "2");
  });

  it("renders the already-revealed state on load when the user already answered today", async () => {
    vi.mocked(api.getGuessThePlayer).mockResolvedValue(
      promptResponse({
        already_answered: true,
        last_result: "correct",
        correct_player: { player_id: "1", name: "Bench Runner", team: "KC", position: "RB", tier: "depth" },
      }),
    );
    render(<GuessThePlayerCard />);

    await screen.findByText("Correct!");
    expect(screen.getAllByText("Bench Runner").length).toBeGreaterThanOrEqual(1);
    expect(api.answerGuessThePlayer).not.toHaveBeenCalled();
  });

  it("is dismissible via the close button", async () => {
    vi.mocked(api.getGuessThePlayer).mockResolvedValue(promptResponse());
    const { container } = render(<GuessThePlayerCard />);

    await screen.findByText("Whose stats are these?");
    fireEvent.click(screen.getByLabelText("Dismiss Guess the Player"));

    expect(container).toBeEmptyDOMElement();
  });

  // coridian_, 2026-10-19: "if you exit that module out, it shouldn't pop
  // back up" -- real bug. Dismiss used to be plain useState, scoped to
  // "this page view" only, so a fresh mount (navigating away and back to
  // Dashboard) reset it and the card reappeared immediately. A real
  // remount is the actual repro -- re-rendering the SAME mounted instance
  // would never have caught this.
  it("stays dismissed across a fresh remount for the same day's pick", async () => {
    vi.mocked(api.getGuessThePlayer).mockResolvedValue(promptResponse());
    const first = render(<GuessThePlayerCard />);
    await screen.findByText("Whose stats are these?");
    fireEvent.click(screen.getByLabelText("Dismiss Guess the Player"));
    expect(first.container).toBeEmptyDOMElement();
    first.unmount();

    vi.mocked(api.getGuessThePlayer).mockResolvedValue(promptResponse());
    const second = render(<GuessThePlayerCard />);
    await waitFor(() => expect(api.getGuessThePlayer).toHaveBeenCalledTimes(2));
    expect(second.container).toBeEmptyDOMElement();
  });

  it("shows again for a NEW day's different pick_id despite a stale dismiss", async () => {
    vi.mocked(api.getGuessThePlayer).mockResolvedValue(promptResponse());
    const first = render(<GuessThePlayerCard />);
    await screen.findByText("Whose stats are these?");
    fireEvent.click(screen.getByLabelText("Dismiss Guess the Player"));
    first.unmount();

    const dayTwo = promptResponse();
    dayTwo.prompt!.pick_id = "pick-2";
    vi.mocked(api.getGuessThePlayer).mockResolvedValue(dayTwo);
    render(<GuessThePlayerCard />);
    await screen.findByText("Whose stats are these?");
  });

  it("disables options once answered so a second click cannot double-submit", async () => {
    vi.mocked(api.getGuessThePlayer).mockResolvedValue(promptResponse());
    vi.mocked(api.answerGuessThePlayer).mockResolvedValue(answerResponse());
    render(<GuessThePlayerCard />);

    const option = await screen.findByRole("radio", { name: "Bench Runner" });
    fireEvent.click(option);
    await waitFor(() => expect(screen.getByText("Correct!")).toBeInTheDocument());

    expect(screen.getByRole("radio", { name: "Bench Runner" })).toBeDisabled();
    expect(screen.getByRole("radio", { name: "Other Back" })).toBeDisabled();
    expect(api.answerGuessThePlayer).toHaveBeenCalledTimes(1);
  });
});
