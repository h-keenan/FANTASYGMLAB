import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { OnboardingPaywall } from "./OnboardingPaywall";
import { api, type BillingPlan } from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      getBillingPlans: vi.fn(),
      startBillingCheckout: vi.fn(),
    },
  };
});

const PLANS: BillingPlan[] = [
  { tier: "pro", interval: "monthly", label: "Monthly", price: "$9.99", cadence: "per month", features: ["Full League Pulse"] },
  {
    tier: "pro",
    interval: "annual",
    label: "Annual",
    price: "$59.99",
    cadence: "per year",
    features: ["Full League Pulse", "Every Trade Hub idea", "GM Targets watchlist up to 50 players", "Portfolio across every league", "Complete waiver board"],
  },
];

describe("OnboardingPaywall", () => {
  beforeEach(() => {
    vi.mocked(api.getBillingPlans).mockReset();
    vi.mocked(api.startBillingCheckout).mockReset();
  });

  // Zach: "have one product here and call it Get Started For Free with a
  // few bullets", then immediately after seeing it live: "have an annual
  // button instead of showing the plan" — one button for the annual plan,
  // price disclosed as fine print below it, no card or feature list.
  it("renders a single Get Started For Free button for the annual plan, no card or bullets", async () => {
    vi.mocked(api.getBillingPlans).mockResolvedValue({ ok: true, plans: PLANS, stripe_publishable_key: "pk_test_123" });
    render(<OnboardingPaywall onSkip={vi.fn()} />);

    expect(await screen.findByRole("button", { name: "Get Started For Free" })).toBeInTheDocument();
    expect(screen.getByText(/Then \$59\.99 per year/)).toBeInTheDocument();
    expect(screen.queryByText("$9.99")).not.toBeInTheDocument();
    expect(screen.queryByText("Full League Pulse")).not.toBeInTheDocument();
  });

  it("calls onSkip when 'Skip for now' is clicked", async () => {
    vi.mocked(api.getBillingPlans).mockResolvedValue({ ok: true, plans: PLANS, stripe_publishable_key: "pk_test_123" });
    const onSkip = vi.fn();
    render(<OnboardingPaywall onSkip={onSkip} />);

    await screen.findByRole("button", { name: "Get Started For Free" });
    fireEvent.click(screen.getByText("Skip for now — continue free"));

    expect(onSkip).toHaveBeenCalledTimes(1);
  });

  it("starts embedded checkout for the annual plan with return_to='/' so a purchase resumes onboarding", async () => {
    vi.mocked(api.getBillingPlans).mockResolvedValue({ ok: true, plans: PLANS, stripe_publishable_key: "pk_test_123" });
    vi.mocked(api.startBillingCheckout).mockResolvedValue({
      ok: true,
      client_secret: "cs_test_onboarding_embedded",
    });
    render(<OnboardingPaywall onSkip={vi.fn()} />);

    fireEvent.click(await screen.findByRole("button", { name: "Get Started For Free" }));

    expect(await screen.findByLabelText("Close checkout")).toBeInTheDocument();
    expect(api.startBillingCheckout).toHaveBeenCalledWith("pro", "annual", "/", "embedded");
  });

  it("shows an error instead of plans when they fail to load", async () => {
    vi.mocked(api.getBillingPlans).mockRejectedValue(new Error("Could not load plans."));
    render(<OnboardingPaywall onSkip={vi.fn()} />);

    expect(await screen.findByText("Could not load plans.")).toBeInTheDocument();
  });
});
