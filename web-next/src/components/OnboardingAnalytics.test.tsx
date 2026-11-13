import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const trackUse = vi.hoisted(() => vi.fn());
vi.mock("@/lib/analytics", () => ({ trackUse, trackFeatureUse: vi.fn() }));
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

import { OnboardingCarousel } from "./OnboardingCarousel";
import { resetOnboardingAnalytics } from "@/lib/onboardingAnalytics";

const calls = () => trackUse.mock.calls.map(([feature, action, opts]) => ({ feature, action, ...opts.props }));

describe("onboarding funnel analytics", () => {
  beforeEach(() => {
    trackUse.mockClear();
    resetOnboardingAnalytics();
  });

  it("fires step_viewed once per step, even after Back/Next revisits and re-renders", async () => {
    const { rerender } = render(<OnboardingCarousel onDone={vi.fn()} />);
    rerender(<OnboardingCarousel onDone={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /veteran dynasty manager/i }));
    fireEvent.click(screen.getByRole("button", { name: /^continue$/i }));
    fireEvent.click(await screen.findByRole("button", { name: "Back" }));
    fireEvent.click(screen.getByRole("button", { name: /^continue$/i }));
    await screen.findByRole("button", { name: "Connect my league" });
    const viewed = calls().filter((c) => c.action === "step_viewed");
    expect(viewed.map((c) => c.step)).toEqual(["level", "value"]);
    expect(viewed.map((c) => c.step_index)).toEqual([0, 1]);
    expect(calls().filter((c) => c.action === "back")).toHaveLength(1);
  });

  it("tracks skipped with the current step, and Decide later leaves the intro in one tap", () => {
    const onDone = vi.fn();
    render(<OnboardingCarousel onDone={onDone} />);
    fireEvent.click(screen.getByRole("button", { name: "Decide later" }));
    expect(calls().find((c) => c.action === "skipped")).toMatchObject({ feature: "onboarding", step: "level", step_index: 0 });
    expect(onDone).toHaveBeenCalledTimes(1);
  });

  it("tracks experience_selected (new|expert) and completed with only allowlisted fixed props", async () => {
    render(<OnboardingCarousel onDone={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /veteran dynasty manager/i }));
    fireEvent.click(screen.getByRole("button", { name: /^continue$/i }));
    await screen.findByRole("button", { name: "Connect my league" });
    const all = calls();
    expect(all.find((c) => c.action === "experience_selected")).toMatchObject({ experience: "expert" });
    expect(all.find((c) => c.action === "completed")).toMatchObject({ experience: "expert", step: "level", step_index: 0 });
    for (const c of all) {
      expect(Object.keys(c).every((k) => ["feature", "action", "step", "step_index", "experience"].includes(k))).toBe(true);
    }
  });

  it("buckets the new, more granular level as 'new' too", () => {
    render(<OnboardingCarousel onDone={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /new to fantasy football/i }));
    expect(calls().find((c) => c.action === "experience_selected")).toMatchObject({ experience: "new" });
  });
});
