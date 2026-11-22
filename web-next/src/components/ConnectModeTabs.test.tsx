import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const trackOnboarding = vi.fn();
vi.mock("@/lib/onboardingAnalytics", () => ({ trackOnboarding: (...a: unknown[]) => trackOnboarding(...a) }));
vi.mock("@/lib/analytics", () => ({ trackFeatureUse: vi.fn(), trackUse: vi.fn() }));

import { ConnectModeTabs } from "@/components/ConnectModeTabs";

describe("ConnectModeTabs", () => {
  beforeEach(() => trackOnboarding.mockClear());

  it("shows the connect form by default", () => {
    render(<ConnectModeTabs><div>connect form</div></ConnectModeTabs>);
    expect(screen.getByText("connect form")).toBeTruthy();
  });

  it("sample tab links to the sample league", () => {
    render(<ConnectModeTabs><div>connect form</div></ConnectModeTabs>);
    fireEvent.click(screen.getByText("Try a sample league"));
    expect(screen.getByTestId("sample-league-button").getAttribute("href")).toBe("/sample-league");
    expect(screen.queryByText("connect form")).toBeNull();
  });

  it("sim tab deep links to the quick start and tracks sim_selected", () => {
    render(<ConnectModeTabs><div>connect form</div></ConnectModeTabs>);
    fireEvent.click(screen.getByText("Play Fantasy Sim"));
    const link = screen.getByTestId("sim-quickstart-button");
    expect(link.getAttribute("href")).toBe("/gm-game?quickstart=1");
    fireEvent.click(link);
    expect(trackOnboarding).toHaveBeenCalledWith("sim_selected", expect.objectContaining({ step: "connect" }));
  });
});
