import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { OnboardingPaywall } from "./OnboardingPaywall";
import { api, type BillingPlan } from "@/lib/api";

const authState = vi.hoisted(() => ({ isGuest: false }));
vi.mock("@/context/AuthContext", () => ({
  useAuth: () => ({
    isGuest: authState.isGuest,
    session: null,
    signIn: vi.fn(),
    signUp: vi.fn(),
    signInWithOAuth: vi.fn(),
  }),
}));
import { ONBOARDING_STEP_KEYS } from "@/lib/onboardingFeatures";
import * as onboardingAnalytics from "@/lib/onboardingAnalytics";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      getBillingPlans: vi.fn(),
      getMe: vi.fn(),
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
    vi.mocked(api.getMe).mockReset();
    vi.mocked(api.getMe).mockRejectedValue(new Error("offline"));
    vi.mocked(api.startBillingCheckout).mockReset();
  });

  // Zach: "have one product here and call it Get Started For Free with a
  // few bullets", then immediately after seeing it live: "have an annual
  // button instead of showing the plan" — one button for the annual plan,
  // price disclosed as fine print below it, no card or feature list.
  it("renders a single trial button for the annual plan, no card or bullets", async () => {
    vi.mocked(api.getBillingPlans).mockResolvedValue({
      ok: true,
      plans: PLANS,
      stripe_publishable_key: "pk_test_123",
      trial: { days: 3, eligible: true },
    });
    render(<OnboardingPaywall onSkip={vi.fn()} />);

    expect(await screen.findByRole("button", { name: "Start 3-day free trial" })).toBeInTheDocument();
    expect(screen.getByText("Then $59.99/year. Cancel anytime.")).toBeInTheDocument();
    expect(screen.queryByText("$9.99")).not.toBeInTheDocument();
    expect(screen.queryByText("Full League Pulse")).not.toBeInTheDocument();
  });

  it("shows no trial copy when the account is not eligible", async () => {
    vi.mocked(api.getBillingPlans).mockResolvedValue({
      ok: true,
      plans: PLANS,
      stripe_publishable_key: "pk_test_123",
      trial: { days: 0, eligible: false },
    });
    render(<OnboardingPaywall onSkip={vi.fn()} />);

    expect(await screen.findByRole("button", { name: "Subscribe" })).toBeInTheDocument();
    expect(screen.queryByText(/free trial/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/free for/i)).not.toBeInTheDocument();
  });

  it("guest sees the create-account gate instead of Start trial and checkout is never called", async () => {
    authState.isGuest = true;
    try {
      vi.mocked(api.getBillingPlans).mockResolvedValue({ ok: true, plans: PLANS, stripe_publishable_key: "pk_test_123" });
      render(<OnboardingPaywall onSkip={vi.fn()} />);
      expect(await screen.findByText("Create an account to start your free trial.")).toBeInTheDocument();
      expect(screen.queryByRole("button", { name: "Subscribe" })).toBeNull();
      fireEvent.click(screen.getByRole("button", { name: "Create account" }));
      expect(screen.getByLabelText("Continue with Google")).toBeInTheDocument();
      expect(api.startBillingCheckout).not.toHaveBeenCalled();
    } finally {
      authState.isGuest = false;
    }
  });

  it("calls onSkip when 'Skip for now' is clicked", async () => {
    vi.mocked(api.getBillingPlans).mockResolvedValue({ ok: true, plans: PLANS, stripe_publishable_key: "pk_test_123" });
    const onSkip = vi.fn();
    render(<OnboardingPaywall onSkip={onSkip} />);

    await screen.findByRole("button", { name: "Subscribe" });
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

    fireEvent.click(await screen.findByRole("button", { name: "Subscribe" }));

    expect(await screen.findByLabelText("Close checkout")).toBeInTheDocument();
    expect(api.startBillingCheckout).toHaveBeenCalledWith("pro", "annual", "/", "embedded");
  });

  it("shows an error instead of plans when they fail to load", async () => {
    vi.mocked(api.getBillingPlans).mockRejectedValue(new Error("Could not load plans."));
    render(<OnboardingPaywall onSkip={vi.fn()} />);

    expect(await screen.findByText("Could not load plans.")).toBeInTheDocument();
  });

  it("reports the paywall step right after the carousel's last step (not a stale index)", () => {
    const spy = vi.spyOn(onboardingAnalytics, "trackOnboardingStepViewed").mockImplementation(() => {});
    vi.mocked(api.getBillingPlans).mockResolvedValue({
      ok: true,
      plans: PLANS,
      stripe_publishable_key: "pk_test_123",
      trial: { days: 3, eligible: true },
    });
    render(<OnboardingPaywall onSkip={vi.fn()} />);
    expect(spy).toHaveBeenCalledWith("paywall", ONBOARDING_STEP_KEYS.length);
    spy.mockRestore();
  });

  it("shows the Free vs Pro table from the server, falling back to static rows", async () => {
    vi.mocked(api.getBillingPlans).mockResolvedValue({
      ok: true,
      plans: PLANS,
      stripe_publishable_key: "pk_test_123",
      trial: { days: 3, eligible: true },
    });
    const { unmount } = render(<OnboardingPaywall onSkip={vi.fn()} />);
    // getMe rejected: static fallback rows render.
    expect(await screen.findByRole("rowheader", { name: "GM Targets" })).toBeTruthy();
    expect(screen.getByText("3 players")).toBeTruthy();
    unmount();

    vi.mocked(api.getMe).mockResolvedValue({
      ok: true,
      user: {} as never,
      premium_benefits: [],
      premium_comparison: [{ key: "gm_targets", label: "GM Targets", free: "9 players", pro: "99 players" }],
    });
    render(<OnboardingPaywall onSkip={vi.fn()} />);
    expect(await screen.findByText("99 players")).toBeTruthy();
  });
});
