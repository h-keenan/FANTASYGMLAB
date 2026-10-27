import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PublicPricingContent } from "./PublicPricingContent";
import { readProtectedReturnPath } from "@/lib/protectedRouteReturn";

const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush, replace: vi.fn() }),
}));

beforeEach(() => {
  mockPush.mockClear();
  window.localStorage.clear();
  window.history.pushState({}, "", "/premium");
});

describe("PublicPricingContent", () => {
  it("renders the offline fallback plans when the public fetch fails", async () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false });
    render(<PublicPricingContent />);

    expect(screen.getByRole("heading", { name: "Unlock the full GM toolkit" })).toBeInTheDocument();
    await waitFor(() => expect(global.fetch).toHaveBeenCalled());
    expect(screen.getByText("$3.99")).toBeInTheDocument();
    expect(screen.getByText("$19.99")).toBeInTheDocument();
  });

  it("swaps in live plan data when the public billing-plans function responds", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        ok: true,
        plans: [{ tier: "pro", interval: "monthly", label: "Monthly", price: "$4.99", cadence: "per month", features: ["A live feature"] }],
      }),
    });
    render(<PublicPricingContent />);

    expect(await screen.findByText("$4.99")).toBeInTheDocument();
    expect(screen.getByText("A live feature")).toBeInTheDocument();
  });

  it("stores the current path before sending a visitor to create an account", () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false });
    render(<PublicPricingContent />);

    fireEvent.click(screen.getByRole("button", { name: "Create your account" }));
    expect(readProtectedReturnPath(window.localStorage)).toBe("/premium");
    expect(mockPush).toHaveBeenCalledWith("/");
  });

  it("offers a plain sign-in link for an existing account", () => {
    global.fetch = vi.fn().mockResolvedValue({ ok: false });
    render(<PublicPricingContent />);

    expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/");
  });
});
