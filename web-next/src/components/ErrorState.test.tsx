import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ErrorState } from "./ErrorState";
import { FREE_LEAGUE_CAP_MESSAGE, isFreeLeagueLockedBody } from "@/lib/freeLeagueCap";

describe("Free league cap", () => {
  it("renders the locked upgrade card instead of an error", () => {
    render(<ErrorState message={FREE_LEAGUE_CAP_MESSAGE} />);
    expect(screen.queryByTestId("error-state")).toBeNull();
    expect(screen.getByText("Your Free plan includes one league")).toBeTruthy();
  });

  it("recognises only the locked league payload", () => {
    expect(isFreeLeagueLockedBody({ league_locked: true, reason: "free_league_cap" })).toBe(true);
    expect(isFreeLeagueLockedBody({ reason: "free_league_cap" })).toBe(false);
    expect(isFreeLeagueLockedBody(null)).toBe(false);
  });
});

describe("ErrorState", () => {
  it("shows the message and calls onRetry when the button is pressed", () => {
    const onRetry = vi.fn();
    render(<ErrorState message="The request timed out. Check your connection and try again." onRetry={onRetry} />);

    expect(screen.getByRole("alert")).toHaveTextContent("The request timed out");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
