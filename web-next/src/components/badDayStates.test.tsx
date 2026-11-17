import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ErrorState } from "./ErrorState";
import { OfflineBanner } from "./OfflineBanner";
import { SlowLoadNote } from "./SlowLoadNote";
import {
  BACK_ONLINE_TEXT,
  LEAGUE_GONE_ACTION,
  OFFLINE_BANNER_TEXT,
  SERVER_ERROR_MESSAGE,
  SESSION_EXPIRED_ACTION,
  SLOW_LOAD_AFTER_MS,
  SLOW_LOAD_RETRY_AFTER_MS,
  SLOW_LOAD_TEXT,
  friendlyStatusMessage,
} from "@/lib/badDayCopy";

describe("bad-day states", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("offline banner follows the window events and says back online briefly", () => {
    render(<OfflineBanner />);
    expect(screen.queryByTestId("offline-banner")).toBeNull();
    const onLine = vi.spyOn(window.navigator, "onLine", "get");
    onLine.mockReturnValue(false);
    act(() => void window.dispatchEvent(new Event("offline")));
    act(() => void vi.advanceTimersByTime(10));
    expect(screen.getByTestId("offline-banner")).toHaveTextContent(OFFLINE_BANNER_TEXT);
    onLine.mockReturnValue(true);
    act(() => void window.dispatchEvent(new Event("online")));
    act(() => void vi.advanceTimersByTime(10));
    expect(screen.getByTestId("offline-banner")).toHaveTextContent(BACK_ONLINE_TEXT);
    act(() => void vi.advanceTimersByTime(3100));
    expect(screen.queryByTestId("offline-banner")).toBeNull();
    onLine.mockRestore();
  });

  it("a skeleton says it is slow after 8s and offers a retry after 15s, never silently", () => {
    const onRetry = vi.fn();
    render(<SlowLoadNote onRetry={onRetry} />);
    expect(screen.queryByTestId("slow-load-note")).toBeNull();
    act(() => void vi.advanceTimersByTime(SLOW_LOAD_AFTER_MS + 10));
    expect(screen.getByTestId("slow-load-note")).toHaveTextContent(SLOW_LOAD_TEXT);
    expect(screen.queryByRole("button")).toBeNull();
    act(() => void vi.advanceTimersByTime(SLOW_LOAD_RETRY_AFTER_MS));
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("an ended session gets a clean sign-in action, not a bare error", () => {
    render(<ErrorState message="Not signed in." />);
    expect(screen.getByTestId("error-state-session")).toBeTruthy();
    expect(screen.getByRole("button", { name: SESSION_EXPIRED_ACTION })).toBeTruthy();
  });

  it("a deleted or archived league offers another league", () => {
    render(<ErrorState message="League not found." />);
    expect(screen.getByTestId("error-state-league-gone")).toBeTruthy();
    expect(screen.getByRole("button", { name: LEAGUE_GONE_ACTION })).toBeTruthy();
  });

  it("a 5xx reads as a sentence with the shared retry", () => {
    const onRetry = vi.fn();
    render(<ErrorState message={friendlyStatusMessage(500, "")} onRetry={onRetry} />);
    expect(screen.getByRole("alert")).toHaveTextContent(SERVER_ERROR_MESSAGE);
    expect(screen.getByRole("alert")).not.toHaveTextContent("500");
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });
});
