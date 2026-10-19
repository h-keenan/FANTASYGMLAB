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
  { tier: "pro", interval: "annual", label: "Annual", price: "$59.99", cadence: "per year", features: ["Full League Pulse"] },
  {
    tier: "front_office",
    interval: "annual",
    label: "Annual",
    price: "$99.99",
    cadence: "per year",
    features: ["Everything in Pro"],
  },
];

describe("OnboardingPaywall", () => {
  beforeEach(() => {
    vi.mocked(api.getBillingPlans).mockReset();
    vi.mocked(api.startBillingCheckout).mockReset();
  });

  it("loads and renders all 3 plans", async () => {
    vi.mocked(api.getBillingPlans).mockResolvedValue({ ok: true, plans: PLANS, stripe_publishable_key: "pk_test_123" });
    render(<OnboardingPaywall onSkip={vi.fn()} />);

    expect(await screen.findByText("$9.99")).toBeInTheDocument();
    expect(screen.getByText("$59.99")).toBeInTheDocument();
    expect(screen.getByText("$99.99")).toBeInTheDocument();
  });

  it("calls onSkip when 'Skip for now' is clicked", async () => {
    vi.mocked(api.getBillingPlans).mockResolvedValue({ ok: true, plans: PLANS, stripe_publishable_key: "pk_test_123" });
    const onSkip = vi.fn();
    render(<OnboardingPaywall onSkip={onSkip} />);

    await screen.findByText("$9.99");
    fireEvent.click(screen.getByText("Skip for now — continue free"));

    expect(onSkip).toHaveBeenCalledTimes(1);
  });

  it("starts embedded checkout with return_to='/' so a purchase resumes onboarding", async () => {
    vi.mocked(api.getBillingPlans).mockResolvedValue({ ok: true, plans: PLANS, stripe_publishable_key: "pk_test_123" });
    vi.mocked(api.startBillingCheckout).mockResolvedValue({
      ok: true,
      client_secret: "cs_test_onboarding_embedded",
    });
    render(<OnboardingPaywall onSkip={vi.fn()} />);

    await screen.findByText("$9.99");
    fireEvent.click(screen.getAllByRole("button", { name: "Subscribe" })[0]);

    expect(await screen.findByLabelText("Close checkout")).toBeInTheDocument();
    expect(api.startBillingCheckout).toHaveBeenCalledWith("pro", "monthly", "/", "embedded");
  });

  it("shows an error instead of plans when they fail to load", async () => {
    vi.mocked(api.getBillingPlans).mockRejectedValue(new Error("Could not load plans."));
    render(<OnboardingPaywall onSkip={vi.fn()} />);

    expect(await screen.findByText("Could not load plans.")).toBeInTheDocument();
  });
});
