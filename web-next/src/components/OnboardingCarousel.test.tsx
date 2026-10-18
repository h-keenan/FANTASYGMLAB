import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { OnboardingCarousel } from "./OnboardingCarousel";
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

describe("OnboardingCarousel", () => {
  it("walks all 4 steps via Next and calls onDone after picking an experience level", async () => {
    const onDone = vi.fn();
    render(<OnboardingCarousel onDone={onDone} />);

    expect(screen.getByText(/your fantasy front office/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Next" })); // -> what we solve
    expect(screen.getByText(/dynasty data is everywhere/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Next" })); // -> how it works
    expect(screen.getByText(/three steps/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Next" })); // -> experience level
    expect(screen.getByText(/how much dynasty experience/i)).toBeInTheDocument();

    // Can't finish without picking a level.
    expect(screen.getByRole("button", { name: /start my 7-day free trial/i })).toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: /new to dynasty/i }));
    expect(screen.getByRole("button", { name: /start my 7-day free trial/i })).not.toBeDisabled();

    fireEvent.click(screen.getByRole("button", { name: /start my 7-day free trial/i }));

    await waitFor(() => expect(api.setExperienceLevel).toHaveBeenCalledWith("beginner"));
    await waitFor(() => expect(onDone).toHaveBeenCalledTimes(1));
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

    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.click(screen.getByRole("button", { name: /i know my stuff/i }));
    fireEvent.click(screen.getByRole("button", { name: /start my 7-day free trial/i }));

    await waitFor(() => expect(onDone).toHaveBeenCalledTimes(1));
  });
});
