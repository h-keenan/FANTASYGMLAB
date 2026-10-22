import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import LandingPage from "./page";
import { useAuth } from "@/context/AuthContext";
import { supabase } from "@/lib/supabase";
import { trackFeatureUse } from "@/lib/analytics";
import { LANDING_PENDING_ATTR, LANDING_PENDING_SCRIPT, LANDING_ROOT_ID } from "@/lib/landingPending";

vi.mock("@/context/AuthContext", () => ({
  useAuth: vi.fn(),
}));

// Real analytics (lib/analytics.ts) does its own fire-and-forget network
// call -- irrelevant to what this file is testing and would otherwise hit a
// real `fetch` during these component tests.
vi.mock("@/lib/analytics", () => ({
  trackFeatureUse: vi.fn(),
}));

vi.mock("@/lib/supabase", () => ({
  supabase: {
    from: vi.fn(),
  },
}));

const mockReplace = vi.fn();
const mockPush = vi.fn();

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mockReplace, push: mockPush }),
  useSearchParams: () => new URLSearchParams(),
}));

// These child components each have their own real logic/dependencies
// (forms, carousels, Stripe paywall copy) that are irrelevant to this
// file's concern -- whether/when `landing_viewed` fires -- and some of
// them (e.g. SleeperImportForm) pull in @/context/AuthContext themselves,
// which would conflict with the mock above. Stubbed to a one-line marker
// each so tests can assert which branch actually rendered.
vi.mock("@/components/LoadingScreen", () => ({
  LoadingScreen: () => <div>LoadingScreen</div>,
}));
vi.mock("@/components/SignInForm", () => ({
  SignInForm: () => <div>SignInForm</div>,
}));
vi.mock("@/components/OnboardingCarousel", () => ({
  OnboardingCarousel: () => <div>OnboardingCarousel</div>,
}));
vi.mock("@/components/OnboardingPaywall", () => ({
  OnboardingPaywall: () => <div>OnboardingPaywall</div>,
}));
vi.mock("@/components/SleeperImportForm", () => ({
  SleeperImportForm: () => <div>SleeperImportForm</div>,
}));

type MockSession = { user: { id: string } };

function mockAuth(session: MockSession | null, loading = false) {
  vi.mocked(useAuth).mockReturnValue({
    session: session as never,
    loading,
    signIn: vi.fn(),
    signUp: vi.fn(),
    signInWithOAuth: vi.fn(),
    signInAsGuest: vi.fn(),
    signOut: vi.fn(),
    deleteAccount: vi.fn(),
    isGuest: false,
  });
}

function mockSavedLeagues(resolution: { data: Array<{ league_id: string; league_name: string }> } | { reject: true }) {
  vi.mocked(supabase.from).mockReturnValue({
    select:
      "reject" in resolution
        ? vi.fn().mockRejectedValue(new Error("network down"))
        : vi.fn().mockResolvedValue(resolution),
  } as never);
}

/**
 * Audit finding, 2026-10-20 (coridian_: "can you add an analytic for the
 * welcome page?"): "/" had zero analytics of its own -- only the generic
 * path-based page_view from RouteAnalytics.tsx. `landing_viewed` is the
 * event this exact purpose already exists for in modules.launch_analytics.
 * TRACKED_EVENTS/FUNNEL_STEPS; it had simply never been called from
 * web-next (only the legacy Streamlit marketing_landing.py called it).
 *
 * The one real correctness requirement (explicit in the ask): never fire
 * for a signed-in visitor who's about to be auto-redirected straight to
 * their Dashboard/Portfolio -- that's not "viewing the welcome page".
 */
describe("LandingPage welcome-page analytics", () => {
  beforeEach(() => {
    vi.mocked(trackFeatureUse).mockClear();
    mockReplace.mockClear();
    mockPush.mockClear();
  });

  /**
   * SSR conversion: the marketing view is now static server HTML, and a
   * returning signed-in visitor is kept on the LoadingScreen (never a
   * flash of marketing copy) via the landing root's pending flag, which
   * CSS uses to swap the loader in. These pin when that flag is set.
   */
  describe("returning-user pending flag", () => {
    const root = () => document.getElementById(LANDING_ROOT_ID);

    it("keeps the loader up (pending) for a returning visitor being redirected to their Dashboard", async () => {
      mockAuth({ user: { id: "user-1" } });
      mockSavedLeagues({ data: [{ league_id: "league-1", league_name: "My League" }] });
      render(<LandingPage />);

      await waitFor(() => expect(mockReplace).toHaveBeenCalled());
      expect(root()).toHaveAttribute(LANDING_PENDING_ATTR);
    });

    it("keeps the loader up (pending) for a returning visitor being redirected to Portfolio", async () => {
      mockAuth({ user: { id: "user-1" } });
      mockSavedLeagues({
        data: [
          { league_id: "league-1", league_name: "League One" },
          { league_id: "league-2", league_name: "League Two" },
        ],
      });
      render(<LandingPage />);

      await waitFor(() => expect(mockReplace).toHaveBeenCalledWith("/portfolio"));
      expect(root()).toHaveAttribute(LANDING_PENDING_ATTR);
    });

    it("reveals the page once a signed-in visitor's check finds zero saved leagues", async () => {
      mockAuth({ user: { id: "user-1" } });
      mockSavedLeagues({ data: [] });
      render(<LandingPage />);

      expect(await screen.findByText("OnboardingCarousel")).toBeInTheDocument();
      expect(root()).not.toHaveAttribute(LANDING_PENDING_ATTR);
    });

    it("never flags a signed-out visitor as pending", async () => {
      mockAuth(null);
      render(<LandingPage />);

      expect(await screen.findByText("SignInForm")).toBeInTheDocument();
      expect(root()).not.toHaveAttribute(LANDING_PENDING_ATTR);
    });

    it("clears a pending flag the inline script set once auth resolves with no session", async () => {
      mockAuth(null, true);
      const { rerender } = render(<LandingPage />);
      // Simulates the pre-paint script having guessed "returning user" from
      // a stale/expired token: left alone while auth is still loading...
      root()!.setAttribute(LANDING_PENDING_ATTR, "");
      rerender(<LandingPage />);
      expect(root()).toHaveAttribute(LANDING_PENDING_ATTR);

      // ...then corrected once auth resolves to no session.
      mockAuth(null);
      rerender(<LandingPage />);
      expect(await screen.findByText("SignInForm")).toBeInTheDocument();
      expect(root()).not.toHaveAttribute(LANDING_PENDING_ATTR);
    });
  });

  describe("pre-paint inline script", () => {
    function runScriptOn(el: HTMLElement) {
      document.body.appendChild(el);
      new Function(LANDING_PENDING_SCRIPT)();
      return el;
    }

    beforeEach(() => {
      localStorage.clear();
      document.getElementById(LANDING_ROOT_ID)?.remove();
    });

    it("flags the root when a persisted Supabase session token exists", () => {
      localStorage.setItem("sb-abcdefgh-auth-token", "{}");
      const el = document.createElement("div");
      el.id = LANDING_ROOT_ID;
      expect(runScriptOn(el)).toHaveAttribute(LANDING_PENDING_ATTR);
      el.remove();
    });

    it("leaves the root alone for a brand-new visitor (no token)", () => {
      localStorage.setItem("unrelated", "1");
      localStorage.setItem("sb-abcdefgh-auth-token-code-verifier", "x");
      const el = document.createElement("div");
      el.id = LANDING_ROOT_ID;
      expect(runScriptOn(el)).not.toHaveAttribute(LANDING_PENDING_ATTR);
      el.remove();
    });
  });

  it("fires landing_viewed once for a brand-new (signed-out) visitor seeing the sign-in form", async () => {
    mockAuth(null);
    render(<LandingPage />);

    expect(await screen.findByText("SignInForm")).toBeInTheDocument();
    expect(trackFeatureUse).toHaveBeenCalledTimes(1);
    expect(trackFeatureUse).toHaveBeenCalledWith("landing_viewed", { props: { source_surface: "landing_hero" } });
  });

  it("does not fire landing_viewed while auth is still resolving", () => {
    mockAuth(null, true);
    render(<LandingPage />);

    // The marketing content is server-rendered and present regardless; only
    // the auth island's slot is held back until auth resolves.
    expect(screen.getByRole("heading", { name: /Your fantasy front office/ })).toBeInTheDocument();
    expect(screen.queryByText("SignInForm")).toBeNull();
    expect(trackFeatureUse).not.toHaveBeenCalled();
  });

  it("fires landing_viewed once a signed-in visitor with zero saved leagues reaches real onboarding content", async () => {
    mockAuth({ user: { id: "user-1" } });
    mockSavedLeagues({ data: [] });
    render(<LandingPage />);

    expect(await screen.findByText("OnboardingCarousel")).toBeInTheDocument();
    expect(trackFeatureUse).toHaveBeenCalledTimes(1);
    expect(trackFeatureUse).toHaveBeenCalledWith("landing_viewed", { props: { source_surface: "landing_hero" } });
    expect(mockReplace).not.toHaveBeenCalled();
  });

  it("never fires landing_viewed for a returning visitor auto-redirected to their single saved league's Dashboard", async () => {
    mockAuth({ user: { id: "user-1" } });
    mockSavedLeagues({ data: [{ league_id: "league-1", league_name: "My League" }] });
    render(<LandingPage />);

    await waitFor(() => expect(mockReplace).toHaveBeenCalledWith("/dashboard/league-1?name=My%20League"));
    expect(trackFeatureUse).not.toHaveBeenCalled();
  });

  it("never fires landing_viewed for a returning visitor auto-redirected to Portfolio (2+ saved leagues)", async () => {
    mockAuth({ user: { id: "user-1" } });
    mockSavedLeagues({
      data: [
        { league_id: "league-1", league_name: "League One" },
        { league_id: "league-2", league_name: "League Two" },
      ],
    });
    render(<LandingPage />);

    await waitFor(() => expect(mockReplace).toHaveBeenCalledWith("/portfolio"));
    expect(trackFeatureUse).not.toHaveBeenCalled();
  });

  it("fires landing_viewed once the saved-leagues check fails and falls through to real content", async () => {
    mockAuth({ user: { id: "user-1" } });
    mockSavedLeagues({ reject: true });
    render(<LandingPage />);

    expect(await screen.findByText("OnboardingCarousel")).toBeInTheDocument();
    expect(trackFeatureUse).toHaveBeenCalledTimes(1);
    expect(trackFeatureUse).toHaveBeenCalledWith("landing_viewed", { props: { source_surface: "landing_hero" } });
  });
});

describe("LandingPage app store modules", () => {
  it("shows App Store coming soon and a live Google Play link to a signed-out visitor", async () => {
    mockAuth(null);
    render(<LandingPage />);

    expect(await screen.findByText("SignInForm")).toBeInTheDocument();
    expect(screen.getByRole("group", { name: /App Store app for iPhone: coming soon/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Get it on Google Play" })).toHaveAttribute(
      "href",
      "https://play.google.com/store/apps/details?id=com.fantasygmlab.app",
    );
  });
});
