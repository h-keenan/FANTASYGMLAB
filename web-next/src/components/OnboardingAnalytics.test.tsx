import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const trackUse = vi.hoisted(() => vi.fn());
vi.mock("@/lib/analytics", () => ({ trackUse }));
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: { ...actual.api, setExperienceLevel: vi.fn().mockResolvedValue({ ok: true }) },
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

  it("fires step_viewed once per step, even after Back/Next revisits and re-renders", () => {
    const { rerender } = render(<OnboardingCarousel onDone={vi.fn()} />);
    rerender(<OnboardingCarousel onDone={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.click(screen.getByRole("button", { name: "Back" }));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    const viewed = calls().filter((c) => c.action === "step_viewed");
    expect(viewed.map((c) => c.step)).toEqual(["gameplan", "tradehub"]);
    expect(viewed.map((c) => c.step_index)).toEqual([0, 1]);
    expect(calls().filter((c) => c.action === "back")).toHaveLength(1);
  });

  it("tracks skipped with the current step", () => {
    render(<OnboardingCarousel onDone={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Skip" }));
    expect(calls().find((c) => c.action === "skipped")).toMatchObject({ feature: "onboarding", step: "gameplan" });
  });

  it("tracks experience_selected (new|expert) and completed with only allowlisted fixed props", () => {
    render(<OnboardingCarousel onDone={vi.fn()} />);
    for (let i = 0; i < 9; i += 1) fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.click(screen.getByRole("button", { name: /i know my stuff/i }));
    fireEvent.click(screen.getByRole("button", { name: /start my 7-day free trial/i }));
    const all = calls();
    expect(all.find((c) => c.action === "experience_selected")).toMatchObject({ experience: "expert" });
    expect(all.find((c) => c.action === "completed")).toMatchObject({ experience: "expert", step: "level" });
    for (const c of all) {
      expect(Object.keys(c).every((k) => ["feature", "action", "step", "step_index", "experience"].includes(k))).toBe(true);
    }
  });
});
