import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PremiumContent } from "./PremiumContent";
import { ApiError, api, type BillingPlan } from "@/lib/api";

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

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      startBillingCheckout: vi.fn(),
      openBillingPortal: vi.fn(),
    },
  };
});

const PRO_FEATURES = ["Full League Pulse", "Full waiver board"];
const FRONT_OFFICE_FEATURES = ["Everything in Pro", "Priority support"];

const PLANS: BillingPlan[] = [
  { tier: "pro", interval: "monthly", label: "Monthly", price: "$9.99", cadence: "per month", features: PRO_FEATURES },
  { tier: "pro", interval: "annual", label: "Annual", price: "$59.99", cadence: "per year", features: PRO_FEATURES },
  {
    tier: "front_office",
    interval: "annual",
    label: "Annual",
    price: "$99.99",
    cadence: "per year",
    features: FRONT_OFFICE_FEATURES,
  },
];

function setWindowLocation() {
  const location = { href: "" };
  Object.defineProperty(window, "location", { value: location, writable: true, configurable: true });
  return location;
}

describe("PremiumContent", () => {
  beforeEach(() => {
    vi.mocked(api.startBillingCheckout).mockReset();
    vi.mocked(api.openBillingPortal).mockReset();
  });

  it("renders all 3 plans and no Manage Billing banner for a free account", () => {
    render(<PremiumContent entitlement="free" plans={PLANS} publishableKey="pk_test_123" />);

    expect(screen.getByText("$9.99")).toBeInTheDocument();
    expect(screen.getByText("$59.99")).toBeInTheDocument();
    expect(screen.getByText("$99.99")).toBeInTheDocument();
    expect(screen.queryByText("Manage Billing")).not.toBeInTheDocument();
  });

  it("lists each plan's own features, not a shared generic list", () => {
    render(<PremiumContent entitlement="free" plans={PLANS} publishableKey="pk_test_123" />);

    expect(screen.getAllByText("Full League Pulse")).toHaveLength(2);
    expect(screen.getByText("Priority support")).toBeInTheDocument();
    // Front Office's "Everything in Pro" must not bleed onto the Pro cards.
    expect(screen.getAllByText("Everything in Pro")).toHaveLength(1);
  });

  it("shows Manage Billing for a premium account, alongside the same 3 plans", () => {
    render(<PremiumContent entitlement="premium" plans={PLANS} publishableKey="pk_test_123" />);

    expect(screen.getByText("You're on Premium.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Manage Billing" })).toBeInTheDocument();
    expect(screen.getByText("$99.99")).toBeInTheDocument();
  });

  // Zach, 2026-10-19: "We need to try to embed stripe so theres not a
  // million redirectes" — Subscribe now opens Stripe's embedded Checkout
  // in place instead of redirecting the whole browser away.
  it("opens the embedded checkout modal after Subscribe, requesting embedded ui_mode", async () => {
    vi.mocked(api.startBillingCheckout).mockResolvedValue({
      ok: true,
      client_secret: "cs_test_embedded_123",
    });
    render(<PremiumContent entitlement="free" plans={PLANS} publishableKey="pk_test_123" />);

    fireEvent.click(screen.getAllByRole("button", { name: "Subscribe" })[0]);

    expect(await screen.findByLabelText("Close checkout")).toBeInTheDocument();
    expect(api.startBillingCheckout).toHaveBeenCalledWith("pro", "monthly", undefined, "embedded");
  });

  it("guest sees account-required gate instead of a checkout button and never calls checkout", () => {
    authState.isGuest = true;
    try {
      render(<PremiumContent entitlement="free" plans={PLANS} publishableKey="pk_test_123" />);
      expect(screen.getAllByText("Create an account to start your free trial.").length).toBeGreaterThan(0);
      expect(screen.queryByRole("button", { name: "Subscribe" })).toBeNull();
      fireEvent.click(screen.getAllByRole("button", { name: "Create account" })[0]);
      expect(screen.getAllByLabelText("Continue with Google").length).toBeGreaterThan(0);
      expect(api.startBillingCheckout).not.toHaveBeenCalled();
    } finally {
      authState.isGuest = false;
    }
  });

  it("handles a server account_required error defensively by showing the gate", async () => {
    vi.mocked(api.startBillingCheckout).mockRejectedValue(
      new ApiError(403, "Create an account to start your free trial.", "account_required"),
    );
    render(<PremiumContent entitlement="free" plans={PLANS} publishableKey="pk_test_123" />);
    fireEvent.click(screen.getAllByRole("button", { name: "Subscribe" })[0]);
    expect((await screen.findAllByText("Create an account to start your free trial.")).length).toBeGreaterThan(0);
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("shows an error instead of redirecting when checkout fails to start", async () => {
    setWindowLocation();
    vi.mocked(api.startBillingCheckout).mockRejectedValue(new Error("Could not start checkout."));
    render(<PremiumContent entitlement="free" plans={PLANS} publishableKey="pk_test_123" />);

    fireEvent.click(screen.getAllByRole("button", { name: "Subscribe" })[0]);

    expect(await screen.findByText("Could not start checkout.")).toBeInTheDocument();
  });

  it("redirects to the real billing portal URL after Manage Billing", async () => {
    const location = setWindowLocation();
    vi.mocked(api.openBillingPortal).mockResolvedValue({
      ok: true,
      portal_url: "https://billing.stripe.com/p/session_abc",
    });
    render(<PremiumContent entitlement="premium" plans={PLANS} publishableKey="pk_test_123" />);

    fireEvent.click(screen.getByRole("button", { name: "Manage Billing" }));

    await waitFor(() => expect(location.href).toBe("https://billing.stripe.com/p/session_abc"));
  });

  it("shows trial CTA and one price line only when the trial is offered", () => {
    render(
      <PremiumContent entitlement="free" plans={PLANS} publishableKey="pk" trial={{ days: 3, eligible: true }} />,
    );
    expect(screen.getAllByRole("button", { name: "Start 3-day free trial" })).toHaveLength(2);
    expect(screen.getAllByText("Then $9.99/month. Cancel anytime.")).toHaveLength(1);
    // Front Office gets no trial.
    expect(screen.getAllByRole("button", { name: "Subscribe" })).toHaveLength(1);
  });

  it("shows no trial copy for an ineligible account", () => {
    render(
      <PremiumContent entitlement="free" plans={PLANS} publishableKey="pk" trial={{ days: 0, eligible: false }} />,
    );
    expect(screen.queryByText(/free trial/i)).not.toBeInTheDocument();
  });

  it("shows the trial end date while trialing", () => {
    const end = new Date(Date.now() + 2 * 86400000).toISOString();
    render(<PremiumContent entitlement="premium" plans={PLANS} publishableKey="pk" trialEndsAt={end} />);
    expect(screen.getByText(/^Trial ends /)).toBeInTheDocument();
  });
});
