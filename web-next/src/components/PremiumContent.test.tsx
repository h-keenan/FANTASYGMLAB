import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PremiumContent } from "./PremiumContent";
import { api, type BillingPlan } from "@/lib/api";

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
    render(<PremiumContent entitlement="free" plans={PLANS} />);

    expect(screen.getByText("$9.99")).toBeInTheDocument();
    expect(screen.getByText("$59.99")).toBeInTheDocument();
    expect(screen.getByText("$99.99")).toBeInTheDocument();
    expect(screen.queryByText("Manage Billing")).not.toBeInTheDocument();
  });

  it("lists each plan's own features, not a shared generic list", () => {
    render(<PremiumContent entitlement="free" plans={PLANS} />);

    expect(screen.getAllByText("Full League Pulse")).toHaveLength(2);
    expect(screen.getByText("Priority support")).toBeInTheDocument();
    // Front Office's "Everything in Pro" must not bleed onto the Pro cards.
    expect(screen.getAllByText("Everything in Pro")).toHaveLength(1);
  });

  it("shows Manage Billing for a premium account, alongside the same 3 plans", () => {
    render(<PremiumContent entitlement="premium" plans={PLANS} />);

    expect(screen.getByText("You're on Premium.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Manage Billing" })).toBeInTheDocument();
    expect(screen.getByText("$99.99")).toBeInTheDocument();
  });

  it("redirects to the real checkout URL after Subscribe", async () => {
    const location = setWindowLocation();
    vi.mocked(api.startBillingCheckout).mockResolvedValue({
      ok: true,
      checkout_url: "https://checkout.stripe.com/pay/cs_test_123",
    });
    render(<PremiumContent entitlement="free" plans={PLANS} />);

    fireEvent.click(screen.getAllByRole("button", { name: "Subscribe" })[0]);

    await waitFor(() => expect(location.href).toBe("https://checkout.stripe.com/pay/cs_test_123"));
    expect(api.startBillingCheckout).toHaveBeenCalledWith("pro", "monthly", undefined);
  });

  it("shows an error instead of redirecting when checkout fails to start", async () => {
    setWindowLocation();
    vi.mocked(api.startBillingCheckout).mockRejectedValue(new Error("Could not start checkout."));
    render(<PremiumContent entitlement="free" plans={PLANS} />);

    fireEvent.click(screen.getAllByRole("button", { name: "Subscribe" })[0]);

    expect(await screen.findByText("Could not start checkout.")).toBeInTheDocument();
  });

  it("redirects to the real billing portal URL after Manage Billing", async () => {
    const location = setWindowLocation();
    vi.mocked(api.openBillingPortal).mockResolvedValue({
      ok: true,
      portal_url: "https://billing.stripe.com/p/session_abc",
    });
    render(<PremiumContent entitlement="premium" plans={PLANS} />);

    fireEvent.click(screen.getByRole("button", { name: "Manage Billing" }));

    await waitFor(() => expect(location.href).toBe("https://billing.stripe.com/p/session_abc"));
  });
});
