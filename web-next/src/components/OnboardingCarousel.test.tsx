import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ONBOARDING_FEATURES, OnboardingCarousel } from "./OnboardingCarousel";
import { api } from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      setExperienceLevel: vi.fn().mockResolvedValue({ ok: true }),
    },
  };
});

const FEATURE_COUNT = ONBOARDING_FEATURES.length;

function clickNext(times: number) {
  for (let i = 0; i < times; i += 1) fireEvent.click(screen.getByRole("button", { name: "Next" }));
}

describe("OnboardingCarousel", () => {
  it("walks every feature slide, then Connect, then the experience picker, and calls onDone after a pick", async () => {
    const onDone = vi.fn();
    render(<OnboardingCarousel onDone={onDone} />);

    // One screenshot-led slide per feature, each with its one-line benefit.
    for (const [index, feature] of ONBOARDING_FEATURES.entries()) {
      expect(screen.getByText(feature.title)).toBeInTheDocument();
      expect(screen.getByText(feature.benefit)).toBeInTheDocument();
      expect(screen.getByRole("img", { name: new RegExp(`${feature.title} screen`) })).toBeInTheDocument();
      if (index < FEATURE_COUNT - 1) clickNext(1);
    }

    clickNext(1); // -> connect
    expect(screen.getByText("Connect Sleeper or ESPN")).toBeInTheDocument();

    clickNext(1); // -> experience level
    expect(screen.getByText(/how much dynasty experience/i)).toBeInTheDocument();

    // Can't finish without picking a level.
    expect(screen.getByRole("button", { name: /start my 7-day free trial/i })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: /new to dynasty/i }));
    expect(screen.getByRole("button", { name: /start my 7-day free trial/i })).not.toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: /start my 7-day free trial/i }));

    await waitFor(() => expect(api.setExperienceLevel).toHaveBeenCalledWith("beginner"));
    await waitFor(() => expect(onDone).toHaveBeenCalledTimes(1));
  });

  it("goes back a slide with Back and advances/retreats on swipe", () => {
    render(<OnboardingCarousel onDone={vi.fn()} />);
    expect(screen.queryByRole("button", { name: "Back" })).not.toBeInTheDocument();

    clickNext(1);
    expect(screen.getByText(ONBOARDING_FEATURES[1].benefit)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    expect(screen.getByText(ONBOARDING_FEATURES[0].benefit)).toBeInTheDocument();

    const content = document.querySelector(".onboarding-content") as HTMLElement;
    fireEvent.touchStart(content, { touches: [{ clientX: 300 }] });
    fireEvent.touchEnd(content, { changedTouches: [{ clientX: 100 }] });
    expect(screen.getByText(ONBOARDING_FEATURES[1].benefit)).toBeInTheDocument();
    fireEvent.touchStart(content, { touches: [{ clientX: 100 }] });
    fireEvent.touchEnd(content, { changedTouches: [{ clientX: 300 }] });
    expect(screen.getByText(ONBOARDING_FEATURES[0].benefit)).toBeInTheDocument();
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

    clickNext(FEATURE_COUNT + 1);
    fireEvent.click(screen.getByRole("button", { name: /i know my stuff/i }));
    fireEvent.click(screen.getByRole("button", { name: /start my 7-day free trial/i }));

    await waitFor(() => expect(onDone).toHaveBeenCalledTimes(1));
  });
});
