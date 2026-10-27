import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import PremiumPage from "./page";
import { useAuth } from "@/context/AuthContext";
import { api } from "@/lib/api";
import { signedIn } from "@/lib/pageFetchTestKit";

vi.mock("@/context/AuthContext", () => ({ useAuth: vi.fn() }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, api: { ...actual.api, getMe: vi.fn(), getBillingPlans: vi.fn() } };
});

vi.mock("@/components/PremiumContent", () => ({
  PremiumContent: () => <div>PremiumContent</div>,
}));

beforeEach(() => {
  vi.clearAllMocks();
  // PublicPricingContent fetches the public billing-plans function in the
  // background; stubbed to fail so every test here exercises the static
  // FALLBACK_PUBLIC_PLANS deterministically instead of a real network call.
  global.fetch = vi.fn().mockResolvedValue({ ok: false });
});

describe("PremiumPage signed-out visitor", () => {
  it("shows public pricing instead of bouncing to / with no content", async () => {
    vi.mocked(useAuth).mockReturnValue({ session: null, loading: false } as unknown as ReturnType<typeof useAuth>);
    render(<PremiumPage />);

    expect(await screen.findByRole("heading", { name: "Unlock the full GM toolkit" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create your account" })).toBeInTheDocument();
    expect(api.getMe).not.toHaveBeenCalled();
    expect(api.getBillingPlans).not.toHaveBeenCalled();
  });

  it("shows a loading state while auth is still resolving, not the pricing page", () => {
    vi.mocked(useAuth).mockReturnValue({ session: null, loading: true } as unknown as ReturnType<typeof useAuth>);
    render(<PremiumPage />);

    expect(screen.queryByRole("heading", { name: "Unlock the full GM toolkit" })).not.toBeInTheDocument();
  });
});

describe("PremiumPage signed-in visitor", () => {
  it("still fetches /v1/me and billing plans and renders the real PremiumContent", async () => {
    vi.mocked(useAuth).mockReturnValue(signedIn as unknown as ReturnType<typeof useAuth>);
    vi.mocked(api.getMe).mockResolvedValue({
      ok: true,
      user: { id: "u1", email: "a@b.com", entitlement: "free", sleeper_username: "", profile_status: "ok", league_cap: 1 },
      premium_benefits: [],
    } as never);
    vi.mocked(api.getBillingPlans).mockResolvedValue({ ok: true, plans: [], stripe_publishable_key: "pk_test" } as never);

    render(<PremiumPage />);

    expect(await screen.findByText("PremiumContent")).toBeInTheDocument();
    await waitFor(() => expect(api.getMe).toHaveBeenCalled());
    expect(api.getBillingPlans).toHaveBeenCalled();
  });

  it("shows an error state when the fetch fails", async () => {
    vi.mocked(useAuth).mockReturnValue(signedIn as unknown as ReturnType<typeof useAuth>);
    vi.mocked(api.getMe).mockRejectedValue(new Error("network down"));
    vi.mocked(api.getBillingPlans).mockResolvedValue({ ok: true, plans: [], stripe_publishable_key: "pk_test" } as never);

    render(<PremiumPage />);

    expect(await screen.findByText("network down")).toBeInTheDocument();
  });
});
