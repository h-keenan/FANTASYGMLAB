import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DirectionCheckinCard } from "./DirectionCheckinCard";
import { api } from "@/lib/api";
import type { DirectionCheckinResponse } from "@/lib/directionCheckin";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: { ...actual.api, getDirectionCheckin: vi.fn(), answerDirectionCheckin: vi.fn(), setTeamStance: vi.fn() },
  };
});

const mocked = api as unknown as Record<string, ReturnType<typeof vi.fn>>;

const SHOW: DirectionCheckinResponse = {
  ok: true, show: true, reason: "", moment: "trade_deadline", moment_key: "2026:trade_deadline", moment_label: "Trade deadline", week: 11,
  stance: "rebuilding", stance_label: "Rebuilding",
  options: [{ value: "competing", label: "Competing" }, { value: "balanced", label: "Balanced" }],
  headline: "Trade deadline: still Rebuilding?", body: "Your trade deadline is close. Does Rebuilding still describe your team?",
  keep_label: "Still fits", dismiss_label: "Not now",
};

describe("DirectionCheckinCard", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mocked.answerDirectionCheckin.mockResolvedValue({ ok: true, show: false });
    mocked.setTeamStance.mockResolvedValue({ ok: true, stance: "competing" });
  });

  it("renders nothing when the server says not to ask, or the read fails", async () => {
    mocked.getDirectionCheckin.mockResolvedValue({ ok: true, show: false, reason: "no_moment" });
    const { container, unmount } = render(<DirectionCheckinCard leagueId="L1" />);
    await waitFor(() => expect(mocked.getDirectionCheckin).toHaveBeenCalledWith("L1"));
    expect(container).toBeEmptyDOMElement();
    unmount();
    mocked.getDirectionCheckin.mockRejectedValue(new Error("down"));
    const again = render(<DirectionCheckinCard leagueId="L1" />);
    await waitFor(() => expect(mocked.getDirectionCheckin).toHaveBeenCalledTimes(2));
    expect(again.container).toBeEmptyDOMElement();
  });

  it("asks with the server's words and offers the other directions", async () => {
    mocked.getDirectionCheckin.mockResolvedValue(SHOW);
    render(<DirectionCheckinCard leagueId="L1" />);
    expect(await screen.findByText("Trade deadline: still Rebuilding?")).toBeInTheDocument();
    expect(screen.getByText(/Does Rebuilding still describe your team/)).toBeInTheDocument();
    for (const name of ["Still fits", "Switch to Competing", "Switch to Balanced", "Not now", "Dismiss direction check-in"]) {
      expect(screen.getByRole("button", { name })).toBeInTheDocument();
    }
  });

  it("Still fits records the answer and closes without touching the direction", async () => {
    mocked.getDirectionCheckin.mockResolvedValue(SHOW);
    render(<DirectionCheckinCard leagueId="L1" />);
    fireEvent.click(await screen.findByRole("button", { name: "Still fits" }));
    await waitFor(() => expect(screen.queryByTestId("direction-checkin")).not.toBeInTheDocument());
    expect(mocked.answerDirectionCheckin).toHaveBeenCalledWith("L1", "2026:trade_deadline", "kept");
    expect(mocked.setTeamStance).not.toHaveBeenCalled();
  });

  it("dismissing (Not now or the X) records a dismissal once and closes", async () => {
    mocked.getDirectionCheckin.mockResolvedValue(SHOW);
    render(<DirectionCheckinCard leagueId="L1" />);
    fireEvent.click(await screen.findByRole("button", { name: "Dismiss direction check-in" }));
    await waitFor(() => expect(screen.queryByTestId("direction-checkin")).not.toBeInTheDocument());
    expect(mocked.answerDirectionCheckin).toHaveBeenCalledTimes(1);
    expect(mocked.answerDirectionCheckin).toHaveBeenCalledWith("L1", "2026:trade_deadline", "dismissed");
    expect(mocked.setTeamStance).not.toHaveBeenCalled();
  });

  it("switching writes the Team Situation, records the change and confirms once", async () => {
    mocked.getDirectionCheckin.mockResolvedValue(SHOW);
    const onChanged = vi.fn();
    render(<DirectionCheckinCard leagueId="L1" onChanged={onChanged} />);
    fireEvent.click(await screen.findByRole("button", { name: "Switch to Competing" }));
    expect(await screen.findByTestId("direction-checkin-done")).toHaveTextContent("Direction set to Competing");
    expect(mocked.setTeamStance).toHaveBeenCalledWith("L1", "competing");
    expect(mocked.answerDirectionCheckin).toHaveBeenCalledWith("L1", "2026:trade_deadline", "changed");
    expect(onChanged).toHaveBeenCalledTimes(1);
  });

  it("a failed switch keeps the card open with an error and records nothing", async () => {
    mocked.getDirectionCheckin.mockResolvedValue(SHOW);
    mocked.setTeamStance.mockRejectedValue(new Error("nope"));
    render(<DirectionCheckinCard leagueId="L1" />);
    fireEvent.click(await screen.findByRole("button", { name: "Switch to Balanced" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not save that. Try again.");
    expect(mocked.answerDirectionCheckin).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Switch to Balanced" })).not.toBeDisabled();
  });

  it("a failed record never reopens the question (the answer already took effect)", async () => {
    mocked.getDirectionCheckin.mockResolvedValue(SHOW);
    mocked.answerDirectionCheckin.mockRejectedValue(new Error("offline"));
    render(<DirectionCheckinCard leagueId="L1" />);
    fireEvent.click(await screen.findByRole("button", { name: "Not now" }));
    await waitFor(() => expect(screen.queryByTestId("direction-checkin")).not.toBeInTheDocument());
    expect(mocked.getDirectionCheckin).toHaveBeenCalledTimes(1);
  });
});
