import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { GmOrb } from "./GmOrb";
import { useAuth } from "@/context/AuthContext";

vi.mock("@/context/AuthContext", () => ({
  useAuth: vi.fn(),
}));

vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard/league-1",
  useParams: () => ({ leagueId: "league-1" }),
  useSearchParams: () => new URLSearchParams(),
}));

type MockSession = { user: { id: string; app_metadata?: Record<string, unknown> } };

function mockAuth(session: MockSession | null) {
  vi.mocked(useAuth).mockReturnValue({
    session: session as never,
    loading: false,
    signIn: vi.fn(),
    signUp: vi.fn(),
    signInWithOAuth: vi.fn(),
    signInAsGuest: vi.fn(),
    signOut: vi.fn(),
    isGuest: false,
  });
}

/**
 * Covers coridian_'s 2026-10-19 ask ("just put it in the orb menu for the
 * specific account(s) listed on supabase") — the GM orb's "Founder" section
 * must only appear for a session whose own Supabase Auth app_metadata
 * carries `founder_ops: true`. This is a client-side UX nicety only: the
 * real authorization boundary is GET /v1/founder/analytics's server-side
 * 403 for anyone without that same claim (services/mobile_api_service.py),
 * covered separately in tests/test_mobile_api_service.py.
 */
describe("GmOrb founder gating", () => {
  it("does not show Founder Analytics for an ordinary signed-in account", () => {
    mockAuth({ user: { id: "user-1" } });
    render(<GmOrb />);

    fireEvent.click(screen.getByLabelText("Open GM menu"));

    expect(screen.queryByText("Founder Analytics")).not.toBeInTheDocument();
  });

  it("does not show Founder Analytics for an account with only a client-editable user_metadata flag", () => {
    // Guards against ever reading the wrong metadata bag — user_metadata is
    // editable by the account itself, unlike app_metadata.
    mockAuth({ user: { id: "user-1", app_metadata: {} } });
    render(<GmOrb />);

    fireEvent.click(screen.getByLabelText("Open GM menu"));

    expect(screen.queryByText("Founder Analytics")).not.toBeInTheDocument();
  });

  it("shows Founder Analytics for a session whose app_metadata carries founder_ops", () => {
    mockAuth({ user: { id: "founder-1", app_metadata: { founder_ops: true } } });
    render(<GmOrb />);

    fireEvent.click(screen.getByLabelText("Open GM menu"));

    expect(screen.getByText("Founder Analytics")).toBeInTheDocument();
  });

  it("renders nothing at all when there is no session", () => {
    mockAuth(null);
    const { container } = render(<GmOrb />);

    expect(container).toBeEmptyDOMElement();
  });
});
