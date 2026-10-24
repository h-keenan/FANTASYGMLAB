import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { EmbeddedCheckoutModal } from "@/components/EmbeddedCheckoutModal";

vi.mock("@stripe/stripe-js", () => ({ loadStripe: vi.fn(() => Promise.resolve(null)) }));
vi.mock("@stripe/react-stripe-js", () => ({
  EmbeddedCheckoutProvider: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  EmbeddedCheckout: () => <div data-testid="stripe-form" />,
}));

describe("EmbeddedCheckoutModal layout", () => {
  it("sizes the overlay in dvh and makes the form region the scroll area, so the submit button is reachable on iOS Safari", () => {
    const { container } = render(<EmbeddedCheckoutModal clientSecret="cs_x" publishableKey="pk_test_x" onClose={() => {}} />);
    const overlay = container.firstElementChild as HTMLElement;
    expect(overlay.style.height).toBe("100dvh");
    const form = screen.getByTestId("stripe-form");
    expect(form.closest(".overflow-y-auto")).not.toBeNull();
    expect(screen.getByLabelText("Close checkout")).toBeInTheDocument();
  });

  it("shows a config message instead of a form when there is no publishable key", () => {
    render(<EmbeddedCheckoutModal clientSecret="cs_x" publishableKey="" onClose={() => {}} />);
    expect(screen.getByText(/isn't configured/)).toBeInTheDocument();
  });
});
