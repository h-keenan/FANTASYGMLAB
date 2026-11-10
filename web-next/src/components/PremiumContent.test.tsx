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

  it("shows one plan at a time (annual first, with the saving), toggles to monthly, and no Manage Billing for a free account", () => {
    render(<PremiumContent entitlement="free" plans={PLANS} publishableKey="pk_test_123" />);

    // Annual is the default, with the real saving: 1 - 59.99 / (9.99 * 12) = 50%.
    expect(screen.getByText("$59.99")).toBeInTheDocument();
    expect(screen.getByText("About $5.00/month, billed yearly")).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Annual · Save 50%/ })).toHaveAttribute("aria-selected", "true");
    expect(screen.queryByText("$9.99")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "Monthly" }));
    expect(screen.getByText("$9.99")).toBeInTheDocument();
    expect(screen.getByText("$99.99")).toBeInTheDocument();
    expect(screen.queryByText("Manage Billing")).not.toBeInTheDocument();
  });

  it("shows the benefits once (3 highlights with the real Free limits), not repeated per plan", () => {
    render(<PremiumContent entitlement="free" plans={PLANS} publishableKey="pk_test_123" />);

    const highlights = screen.getByTestId("pro-highlights");
    expect(highlights.querySelectorAll("li")).toHaveLength(3);
    expect(screen.getByText(/Free shows the top 4/)).toBeInTheDocument();
    expect(screen.getByText(/Free shows the first 2/)).toBeInTheDocument();
    // The old per-plan feature wall is gone.
    expect(screen.queryByText("Full League Pulse")).not.toBeInTheDocument();
    expect(screen.queryByText("Priority support")).not.toBeInTheDocument();
  });

  it("links terms, subscription terms and privacy and offers help", () => {
    render(<PremiumContent entitlement="free" plans={PLANS} publishableKey="pk_test_123" />);
    expect(screen.getByRole("link", { name: "Terms" })).toHaveAttribute("href", "/legal/terms");
    expect(screen.getByRole("link", { name: "Subscription Terms" })).toHaveAttribute("href", "/legal/subscription_terms");
    expect(screen.getByRole("link", { name: "Privacy Policy" })).toHaveAttribute("href", "/legal/privacy");
    expect(screen.getByTestId("help-link")).toBeInTheDocument();
  });

  it("shows Manage Billing for a premium account, alongside the same 3 plans", () => {
    render(<PremiumContent entitlement="premium" plans={PLANS} publishableKey="pk_test_123" />);

    expect(screen.getByText("You're on Pro.")).toBeInTheDocument();
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
    expect(api.startBillingCheckout).toHaveBeenCalledWith("pro", "annual", undefined, "embedded");
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
    expect(screen.getAllByRole("button", { name: "Start 3-day free trial" })).toHaveLength(1);
    expect(screen.getByText(/Then \$59\.99\/year\. Cancel anytime\./)).toBeInTheDocument();
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

  it("renders the Free vs Pro comparison", () => {
    render(<PremiumContent entitlement="free" plans={PLANS} publishableKey="pk_test_123" />);
    // Collapsed behind "Everything in Pro" so it is not a wall of text.
    expect(screen.getByTestId("pro-comparison").tagName).toBe("DETAILS");
    expect(screen.getByRole("rowheader", { name: "Trade Hub ideas", hidden: true })).toBeTruthy();
  });
});
