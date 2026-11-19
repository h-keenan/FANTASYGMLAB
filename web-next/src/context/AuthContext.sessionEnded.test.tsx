import { act, render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/analytics", () => ({ trackFeatureUse: vi.fn() }));

const getSession = vi.fn();
const signOut = vi.fn();
let authCallback: ((event: string, session: unknown) => void) | null = null;

vi.mock("@/lib/supabase", () => ({
  supabase: {
    auth: {
      getSession: (...a: unknown[]) => getSession(...a),
      signOut: (...a: unknown[]) => signOut(...a),
      onAuthStateChange: (cb: (event: string, session: unknown) => void) => {
        authCallback = cb;
        return { data: { subscription: { unsubscribe: vi.fn() } } };
      },
    },
  },
}));

import { AuthProvider, useAuth } from "./AuthContext";

const session = { access_token: "t", user: { id: "u1" } };

describe("AuthContext forced sign-out", () => {
  let value: ReturnType<typeof useAuth> | null = null;
  function Probe() {
    value = useAuth();
    return null;
  }

  beforeEach(() => {
    value = null;
    authCallback = null;
    window.sessionStorage.clear();
    window.localStorage.clear();
    window.history.replaceState({}, "", "/trade-analyzer/L1?name=Mine");
    getSession.mockReset().mockResolvedValue({ data: { session } });
    signOut.mockReset().mockResolvedValue({ error: null });
  });

  async function mount() {
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    await waitFor(() => expect(value?.loading).toBe(false));
  }

  it("a SIGNED_OUT the user did not ask for sets the note and remembers where they were", async () => {
    await mount();
    expect(value?.sessionEnded).toBe(false);
    act(() => authCallback?.("SIGNED_OUT", null));
    await waitFor(() => expect(value?.sessionEnded).toBe(true));
    expect(window.localStorage.getItem("fd_protected_route_return_path")).toContain("/trade-analyzer/L1?name=Mine");
    expect(window.sessionStorage.getItem("fd_session_ended_at")).not.toBeNull();
  });

  it("the user's own sign-out does not", async () => {
    await mount();
    await act(async () => {
      await value?.signOut();
    });
    act(() => authCallback?.("SIGNED_OUT", null));
    expect(value?.sessionEnded).toBe(false);
    expect(window.localStorage.getItem("fd_protected_route_return_path")).toBeNull();
  });

  it("signing back in clears the note", async () => {
    await mount();
    act(() => authCallback?.("SIGNED_OUT", null));
    await waitFor(() => expect(value?.sessionEnded).toBe(true));
    act(() => authCallback?.("SIGNED_IN", session));
    await waitFor(() => expect(value?.sessionEnded).toBe(false));
    expect(window.sessionStorage.getItem("fd_session_ended_at")).toBeNull();
  });

  it("a reload after a forced sign-out still shows the note", async () => {
    getSession.mockResolvedValue({ data: { session: null } });
    window.sessionStorage.setItem("fd_session_ended_at", String(Date.now()));
    await mount();
    expect(value?.sessionEnded).toBe(true);
  });
});
