import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ReferralCard } from "./ReferralCard";
import type { ReferralStatusResponse } from "@/lib/api";

function referral(overrides: Partial<ReferralStatusResponse> = {}): ReferralStatusResponse {
  return {
    ok: true,
    code: "ABC123",
    link: "https://app.fantasygmlab.com/?ref=ABC123",
    connected_count: 0,
    comp_months_granted: 0,
    comp_until: null,
    comp_is_active: false,
    comp_months_remaining_capacity: 3,
    referrals_per_comp_month: 3,
    max_comp_months: 3,
    ...overrides,
  };
}

/** Jsdom doesn't define navigator.clipboard by default -- add/remove it per
 * test as its own configurable property, same helper pattern as
 * TradeIdeaCard.test.tsx's stubClipboard. */
function stubClipboard(impl?: () => Promise<void>) {
  const writeText = vi.fn(impl ?? (() => Promise.resolve()));
  Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true, writable: true });
  return writeText;
}

afterEach(() => {
  delete (navigator as unknown as Record<string, unknown>).clipboard;
  vi.restoreAllMocks();
});

describe("ReferralCard", () => {
  it("shows a loading message while the referral status hasn't loaded yet", () => {
    render(<ReferralCard referral={null} error={null} onRetry={vi.fn()} />);
    expect(screen.getByText("Loading your invite link…")).toBeInTheDocument();
  });

  it("shows the error message and a Retry button that calls onRetry", () => {
    const onRetry = vi.fn();
    render(<ReferralCard referral={null} error="Could not load your invite link." onRetry={onRetry} />);

    expect(screen.getByRole("alert")).toHaveTextContent("Could not load your invite link.");
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("shows the empty state copy when no friends have joined yet", () => {
    render(<ReferralCard referral={referral({ connected_count: 0 })} error={null} onRetry={vi.fn()} />);
    expect(screen.getByText("None yet, share your link")).toBeInTheDocument();
    expect(screen.getByText("0 / 3")).toBeInTheDocument();
  });

  it("shows the populated reward state once referrals have landed", () => {
    render(
      <ReferralCard
        referral={referral({
          connected_count: 3,
          comp_months_granted: 1,
          comp_is_active: true,
          comp_until: "2099-01-01T00:00:00+00:00",
        })}
        error={null}
        onRetry={vi.fn()}
      />,
    );

    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("1 / 3")).toBeInTheDocument();
    expect(screen.getByText(/Active through/)).toBeInTheDocument();
  });

  it("renders the user's own referral link in a read-only field", () => {
    render(<ReferralCard referral={referral({ link: "https://app.fantasygmlab.com/?ref=XYZ" })} error={null} onRetry={vi.fn()} />);
    const input = screen.getByLabelText("Your referral link") as HTMLInputElement;
    expect(input.value).toBe("https://app.fantasygmlab.com/?ref=XYZ");
    expect(input).toHaveAttribute("readonly");
  });

  it("copies the referral link to the clipboard and shows Copied! feedback", async () => {
    const writeText = stubClipboard();
    render(<ReferralCard referral={referral({ link: "https://app.fantasygmlab.com/?ref=XYZ" })} error={null} onRetry={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Copy link" }));
    await screen.findByRole("button", { name: "Copied!" });
    expect(writeText).toHaveBeenCalledWith("https://app.fantasygmlab.com/?ref=XYZ");
  });

  it("fails soft when the clipboard write is rejected", async () => {
    stubClipboard(() => Promise.reject(new Error("denied")));
    render(<ReferralCard referral={referral()} error={null} onRetry={vi.fn()} />);

    fireEvent.click(screen.getByRole("button", { name: "Copy link" }));
    // Still shows the normal label -- never throws into the component.
    expect(await screen.findByRole("button", { name: "Copy link" })).toBeInTheDocument();
  });
});
