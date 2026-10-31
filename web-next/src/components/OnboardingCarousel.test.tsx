import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ONBOARDING_FEATURES, OnboardingCarousel } from "./OnboardingCarousel";
import { ONBOARDING_VALUE_HEADLINE, ONBOARDING_VALUE_SLIDE_MS } from "@/lib/onboardingFeatures";
import { api } from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      setExperienceLevel: vi.fn().mockResolvedValue({ ok: true }),
      setExperienceGoal: vi.fn().mockResolvedValue({ ok: true }),
    },
  };
});

const FEATURE_COUNT = ONBOARDING_FEATURES.length;

function clickNext(times: number) {
  for (let i = 0; i < times; i += 1) fireEvent.click(screen.getByRole("button", { name: "Next" }));
}

describe("OnboardingCarousel", () => {
  it("portals to body and makes the page behind inert while open, restoring it on unmount", () => {
    const page = document.createElement("div");
    document.body.appendChild(page);
    const { unmount } = render(<OnboardingCarousel onDone={vi.fn()} />);
    expect(page).toHaveAttribute("inert");
    expect(page).toHaveAttribute("aria-hidden", "true");
    const root = document.querySelector("[data-onboarding-root]");
    expect(root?.parentElement).toBe(document.body);
    expect(root).not.toHaveAttribute("inert");
    unmount();
    expect(page).not.toHaveAttribute("inert");
    expect(page).not.toHaveAttribute("aria-hidden");
    expect(document.querySelector("[data-onboarding-root]")).toBeNull();
    page.remove();
  });

  it("walks value, then Connect, then the experience picker, and calls onDone after a pick", async () => {
    const onDone = vi.fn();
    render(<OnboardingCarousel onDone={onDone} />);

    // Step 1: one value line over a screenshot with its benefit.
    expect(screen.getByRole("heading", { name: ONBOARDING_VALUE_HEADLINE })).toBeInTheDocument();
    expect(screen.getByText(ONBOARDING_FEATURES[0].benefit)).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /Game Plan screen/ })).toBeInTheDocument();
    expect(document.querySelectorAll(".onboarding-dot")).toHaveLength(3);

    clickNext(1); // -> connect
    expect(screen.getByRole("heading", { name: "Connect Sleeper or ESPN" })).toBeInTheDocument();

    clickNext(1); // -> experience level
    expect(screen.getByRole("heading", { name: /how much dynasty experience/i })).toBeInTheDocument();

    // Can't finish without picking a level.
    expect(screen.getByRole("button", { name: /^continue$/i })).toBeDisabled();

    // All three levels are offered, including the new, more granular one.
    expect(screen.getByRole("button", { name: /new to fantasy football/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /new to dynasty/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /veteran dynasty manager/i })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /new to dynasty/i }));
    expect(screen.getByRole("button", { name: /^continue$/i })).not.toBeDisabled();

    // The goal chip is optional: picking a level alone is enough to continue.
    fireEvent.click(screen.getByRole("tab", { name: /^win now$/i }));
    fireEvent.click(screen.getByRole("button", { name: /^continue$/i }));

    await waitFor(() => expect(api.setExperienceLevel).toHaveBeenCalledWith("beginner"));
    await waitFor(() => expect(api.setExperienceGoal).toHaveBeenCalledWith("win_now"));
    await waitFor(() => expect(onDone).toHaveBeenCalledTimes(1));
  });

  it("lets a brand-new fantasy player pick the most beginner level, and skips the goal chip write when none is picked", async () => {
    const onDone = vi.fn();
    render(<OnboardingCarousel onDone={onDone} />);
    clickNext(2);

    fireEvent.click(screen.getByRole("button", { name: /new to fantasy football/i }));
    fireEvent.click(screen.getByRole("button", { name: /^continue$/i }));

    await waitFor(() => expect(api.setExperienceLevel).toHaveBeenCalledWith("new_to_fantasy"));
    await waitFor(() => expect(onDone).toHaveBeenCalledTimes(1));
    expect(api.setExperienceGoal).not.toHaveBeenCalled();
  });

  it("clears the goal chip on a second click, same as never picking one", async () => {
    const onDone = vi.fn();
    render(<OnboardingCarousel onDone={onDone} />);
    clickNext(2);

    fireEvent.click(screen.getByRole("button", { name: /new to dynasty/i }));
    fireEvent.click(screen.getByRole("tab", { name: /^rebuilding$/i }));
    fireEvent.click(screen.getByRole("tab", { name: /^rebuilding$/i }));
    fireEvent.click(screen.getByRole("button", { name: /^continue$/i }));

    await waitFor(() => expect(onDone).toHaveBeenCalledTimes(1));
    expect(api.setExperienceGoal).not.toHaveBeenCalled();
  });

  it("goes back a slide with Back and advances/retreats on swipe", () => {
    render(<OnboardingCarousel onDone={vi.fn()} />);
    expect(screen.queryByRole("button", { name: "Back" })).not.toBeInTheDocument();

    clickNext(1);
    expect(screen.getByRole("heading", { name: "Connect Sleeper or ESPN" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(screen.getByRole("heading", { name: ONBOARDING_VALUE_HEADLINE })).toBeInTheDocument();

    const content = document.querySelector(".onboarding-content") as HTMLElement;
    fireEvent.touchStart(content, { touches: [{ clientX: 300 }] });
    fireEvent.touchEnd(content, { changedTouches: [{ clientX: 100 }] });
    expect(screen.getByRole("heading", { name: "Connect Sleeper or ESPN" })).toBeInTheDocument();
    fireEvent.touchStart(content, { touches: [{ clientX: 100 }] });
    fireEvent.touchEnd(content, { changedTouches: [{ clientX: 300 }] });
    expect(screen.getByRole("heading", { name: ONBOARDING_VALUE_HEADLINE })).toBeInTheDocument();
  });

  it("calls onDone immediately on Skip, without saving an experience level", () => {
    const onDone = vi.fn();
    render(<OnboardingCarousel onDone={onDone} />);

    fireEvent.click(screen.getByRole("button", { name: "Skip" }));

    expect(onDone).toHaveBeenCalledTimes(1);
    expect(api.setExperienceLevel).not.toHaveBeenCalled();
  });

  it("still calls onDone even when the preference write fails", async () => {
    vi.mocked(api.setExperienceLevel).mockRejectedValueOnce(new Error("network error"));
    const onDone = vi.fn();
    render(<OnboardingCarousel onDone={onDone} />);

    clickNext(2);
    fireEvent.click(screen.getByRole("button", { name: /veteran dynasty manager/i }));
    fireEvent.click(screen.getByRole("button", { name: /^continue$/i }));

    await waitFor(() => expect(onDone).toHaveBeenCalledTimes(1));
  });
});

describe("OnboardingCarousel value step previews", () => {
  it("auto-advances screenshots inside step 1 without adding steps, and pauses on request", () => {
    vi.useFakeTimers();
    try {
      render(<OnboardingCarousel onDone={vi.fn()} />);
      expect(screen.getByRole("img", { name: /Game Plan screen/ })).toBeInTheDocument();
      act(() => {
        vi.advanceTimersByTime(ONBOARDING_VALUE_SLIDE_MS + 50);
      });
      expect(screen.getByRole("img", { name: /Trade Hub screen/ })).toBeInTheDocument();
      expect(screen.getByRole("heading", { name: ONBOARDING_VALUE_HEADLINE })).toBeInTheDocument();
      fireEvent.click(screen.getByRole("button", { name: "Pause previews" }));
      act(() => {
        vi.advanceTimersByTime(ONBOARDING_VALUE_SLIDE_MS * 3);
      });
      expect(screen.getByRole("img", { name: /Trade Hub screen/ })).toBeInTheDocument();
      fireEvent.click(screen.getByRole("button", { name: "Show Waivers" }));
      expect(screen.getByRole("img", { name: /Waivers screen/ })).toBeInTheDocument();
      expect(document.querySelectorAll(".onboarding-dot")).toHaveLength(3);
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("OnboardingCarousel replay", () => {
  it("shows only the feature slides, ends with Done, and never saves a preference", () => {
    const onDone = vi.fn();
    render(<OnboardingCarousel replay onDone={onDone} />);
    clickNext(FEATURE_COUNT - 1);
    expect(screen.queryByRole("button", { name: "Next" })).toBeNull();
    expect(screen.queryByRole("heading", { name: "Connect Sleeper or ESPN" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Done" }));
    expect(onDone).toHaveBeenCalledTimes(1);
    expect(api.setExperienceLevel).not.toHaveBeenCalled();
  });
});
