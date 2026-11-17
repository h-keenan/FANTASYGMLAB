import { act, render, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/lib/analytics", () => ({ trackFeatureUse: vi.fn() }));

const getSession = vi.fn();
const signOut = vi.fn();
vi.mock("@/lib/supabase", () => ({
  supabase: {
    auth: {
      getSession: (...a: unknown[]) => getSession(...a),
      signOut: (...a: unknown[]) => signOut(...a),
      onAuthStateChange: () => ({ data: { subscription: { unsubscribe: vi.fn() } } }),
    },
  },
}));

const billingRequest = vi.fn();
vi.mock("@/lib/billingClient", () => ({
  billingRequest: (...a: unknown[]) => billingRequest(...a),
}));

import { AuthProvider, useAuth } from "./AuthContext";

describe("AuthContext.deleteAccount", () => {
  let auth: ReturnType<typeof useAuth> | null = null;
  function Probe() {
    auth = useAuth();
    return null;
  }
  beforeEach(async () => {
    billingRequest.mockReset();
    signOut.mockReset().mockResolvedValue({});
    getSession.mockReset().mockResolvedValue({ data: { session: { access_token: "tok" } } });
    auth = null;
    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    );
    await waitFor(() => expect(auth).not.toBeNull());
  });

  it("calls the delete-account edge function, then signs out, and never returns the support-only message", async () => {
    billingRequest.mockResolvedValue({ ok: true });
    let result: { error: string | null } | undefined;
    await act(async () => {
      result = await auth!.deleteAccount();
    });
    expect(billingRequest).toHaveBeenCalledWith("delete-account", "tok", expect.objectContaining({ method: "POST", backend: "supabase" }));
    expect(signOut).toHaveBeenCalledTimes(1);
    expect(result).toEqual({ error: null });
  });

  it("returns the server error and does not sign out when deletion fails", async () => {
    billingRequest.mockRejectedValue(new Error("Could not cancel billing, so the account was not deleted."));
    let result: { error: string | null } | undefined;
    await act(async () => {
      result = await auth!.deleteAccount();
    });
    expect(result?.error).toMatch(/not deleted/);
    expect(result?.error).not.toMatch(/Email support|temporarily unavailable/);
    expect(signOut).not.toHaveBeenCalled();
  });
});
