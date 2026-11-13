import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { FirstValueOfferCard } from "@/components/FirstValueOfferCard";
import { trialOfferState } from "@/lib/onboardingProgress";

const trackUse = vi.fn();
vi.mock("@/lib/analytics", () => ({ trackUse: (...a: unknown[]) => trackUse(...a), trackFeatureUse: vi.fn() }));
vi.mock("next/link", () => ({
  default: ({ href, children, ...rest }: { href: string; children: React.ReactNode }) => (
    <a href={href} {...rest}>
      {children}
    </a>
  ),
}));

const actions = () => trackUse.mock.calls.filter((c) => c[0] === "paywall").map((c) => c[1]);

describe("FirstValueOfferCard", () => {
  beforeEach(() => {
    window.localStorage.clear();
    trackUse.mockClear();
  });

  it("renders nothing until the first connect armed it", () => {
    render(<FirstValueOfferCard userId="u1" isPremium={false} />);
    expect(screen.queryByTestId("first-value-offer")).toBeNull();
  });

  it("renders nothing for a Pro account even when armed", () => {
    window.localStorage.setItem("fgl:onboarding:offer_armed:u1", "1");
    render(<FirstValueOfferCard userId="u1" isPremium />);
    expect(screen.queryByTestId("first-value-offer")).toBeNull();
  });

  it("shows once when armed, then Continue free dismisses it for good", () => {
    window.localStorage.setItem("fgl:onboarding:offer_armed:u1", "1");
    const { unmount } = render(<FirstValueOfferCard userId="u1" isPremium={false} />);
    expect(screen.getByTestId("first-value-offer")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "See Pro plans" })).toHaveAttribute("href", "/premium");
    expect(actions()).toEqual(["offer_seen"]);

    fireEvent.click(screen.getByRole("button", { name: "Continue free" }));
    expect(screen.queryByTestId("first-value-offer")).toBeNull();
    expect(actions()).toEqual(["offer_seen", "offer_dismissed"]);
    expect(trialOfferState("u1")).toBe("dismissed");

    unmount();
    render(<FirstValueOfferCard userId="u1" isPremium={false} />);
    expect(screen.queryByTestId("first-value-offer")).toBeNull();
  });

  it("opening the Pro page also resolves the offer so it does not nag on return", () => {
    window.localStorage.setItem("fgl:onboarding:offer_armed:u1", "1");
    render(<FirstValueOfferCard userId="u1" isPremium={false} />);
    fireEvent.click(screen.getByRole("link", { name: "See Pro plans" }));
    expect(actions()).toContain("offer_cta");
    expect(trialOfferState("u1")).toBe("dismissed");
  });
});
