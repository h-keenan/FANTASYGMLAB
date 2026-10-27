import { act, render, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const trackFeatureUse = vi.fn();
vi.mock("@/lib/analytics", () => ({
  trackFeatureUse: (...args: unknown[]) => trackFeatureUse(...args),
}));

const signInWithPassword = vi.fn();
const signUp = vi.fn();
const getSession = vi.fn();
const onAuthStateChange = vi.fn();

vi.mock("@/lib/supabase", () => ({
  supabase: {
    auth: {
      signInWithPassword: (...args: unknown[]) => signInWithPassword(...args),
      signUp: (...args: unknown[]) => signUp(...args),
      getSession: (...args: unknown[]) => getSession(...args),
      onAuthStateChange: (...args: unknown[]) => onAuthStateChange(...args),
    },
  },
}));

import { AuthProvider, useAuth } from "./AuthContext";

/**
 * login_completed / signup_completed / signup_started are real taxonomy
 * events (modules.launch_analytics.TRACKED_EVENTS) that no web-next call
 * site ever fired before this fix (Founder Analytics audit, 2026-10) --
 * these pin the three outcomes AuthContext now instruments.
 */
describe("AuthContext analytics", () => {
  let authValue: ReturnType<typeof useAuth> | null = null;

  function Probe() {
    authValue = useAuth();
    return null;
  }

  beforeEach(() => {
    trackFeatureUse.mockClear();
    signInWithPassword.mockReset();
    signUp.mockReset();
    getSession.mockReset().mockResolvedValue({ data: { session: null } });
    onAuthStateChange.mockReset().mockReturnValue({ data: { subscription: { unsubscribe: vi.fn() } } });
    authValue = null;
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  async function mount() {
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    await waitFor(() => expect(authValue).not.toBeNull());
    return authValue!;
  }

  it("tracks login_completed on a successful password sign-in", async () => {
    signInWithPassword.mockResolvedValue({ error: null });
    const auth = await mount();

    await act(async () => {
      await auth.signIn("person@example.com", "hunter2");
    });

    expect(trackFeatureUse).toHaveBeenCalledWith("login_completed", { dedupe: false });
  });

  it("does not track login_completed when sign-in fails", async () => {
    signInWithPassword.mockResolvedValue({ error: { message: "Invalid credentials" } });
    const auth = await mount();

    await act(async () => {
      await auth.signIn("person@example.com", "wrong");
    });

    expect(trackFeatureUse).not.toHaveBeenCalled();
  });

  it("tracks signup_completed when signUp returns an active session (auto-confirm on)", async () => {
    signUp.mockResolvedValue({
      data: { user: { identities: [{ id: "x" }] }, session: { access_token: "t" } },
      error: null,
    });
    const auth = await mount();

    await act(async () => {
      await auth.signUp("new@example.com", "hunter2");
    });

    expect(trackFeatureUse).toHaveBeenCalledWith("signup_completed", { dedupe: false });
  });

  it("tracks signup_started when signUp requires email confirmation", async () => {
    signUp.mockResolvedValue({
      data: { user: { identities: [{ id: "x" }] }, session: null },
      error: null,
    });
    const auth = await mount();

    await act(async () => {
      await auth.signUp("new@example.com", "hunter2");
    });

    expect(trackFeatureUse).toHaveBeenCalledWith("signup_started", { dedupe: false });
  });

  it("does not track a signup event for the anti-enumeration 'already exists' path", async () => {
    signUp.mockResolvedValue({
      data: { user: { identities: [] }, session: null },
      error: null,
    });
    const auth = await mount();

    await act(async () => {
      await auth.signUp("existing@example.com", "hunter2");
    });

    expect(trackFeatureUse).not.toHaveBeenCalled();
  });
});
