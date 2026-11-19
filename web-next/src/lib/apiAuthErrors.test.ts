import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  BAD_RESPONSE_MESSAGE,
  FORBIDDEN_MESSAGE,
  OFFLINE_ERROR_MESSAGE,
  SERVER_ERROR_MESSAGE,
  classifyErrorMessage,
  friendlyStatusMessage,
  isRetryableSessionLookupError,
} from "./badDayCopy";
import { clearSessionEnded, isForcedSignOut, markSessionEnded, readSessionEnded } from "./sessionEnded";

const getSession = vi.fn();
vi.mock("./supabase", () => ({ supabase: { auth: { getSession: (...a: unknown[]) => getSession(...a) } } }));
vi.mock("./analytics", () => ({ trackClientError: vi.fn(), trackFeatureUse: vi.fn() }));

import { api, ApiError } from "./api";

function jsonResponse(status: number, body: unknown, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json", ...headers } });
}

const signedIn = { data: { session: { access_token: "tok", user: { id: "u1" } } }, error: null };

describe("api auth and transport error paths", () => {
  beforeEach(() => {
    getSession.mockReset().mockResolvedValue(signedIn);
  });
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  async function failure(): Promise<ApiError> {
    try {
      await api.getMe();
    } catch (e) {
      return e as ApiError;
    }
    throw new Error("expected a failure");
  }

  it("an offline token refresh failure reads as offline, never as a signed-out session", async () => {
    getSession.mockResolvedValue({ data: { session: null }, error: { name: "AuthRetryableFetchError", status: 0, message: "Failed to fetch" } });
    const err = await failure();
    expect(err.status).toBe(0);
    expect(err.message).toBe(OFFLINE_ERROR_MESSAGE);
    expect(classifyErrorMessage(err.message)).toBe("offline");
  });

  it("no session and no error is the signed-out message", async () => {
    getSession.mockResolvedValue({ data: { session: null }, error: null });
    const err = await failure();
    expect(err.status).toBe(401);
    expect(classifyErrorMessage(err.message)).toBe("session");
  });

  it("a server 401 routes to the session-ended state whatever text it carries", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(401, { ok: false, error: "Invalid or expired session.", code: "session_invalid" })));
    const err = await failure();
    expect(err.status).toBe(401);
    expect(err.code).toBe("session_invalid");
    expect(classifyErrorMessage(err.message)).toBe("session");
  });

  it("a 503 auth_unavailable keeps its message and Retry-After and is not a session error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(503, { ok: false, error: "We could not check your sign-in just now. Try again in a moment.", code: "auth_unavailable" }, { "Retry-After": "5" }),
      ),
    );
    const err = await failure();
    expect(err.status).toBe(503);
    expect(err.code).toBe("auth_unavailable");
    expect(err.retryAfterSeconds).toBe(5);
    expect(classifyErrorMessage(err.message)).not.toBe("session");
  });

  it("a 2xx HTML body (proxy page) is a clear retryable error, not a null that crashes the screen", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("<html>Bad gateway</html>", { status: 200, headers: { "Content-Type": "text/html" } })));
    const err = await failure();
    expect(err.status).toBe(502);
    expect(err.message).toBe(BAD_RESPONSE_MESSAGE);
    expect(err.code).toBe("bad_response");
  });

  it("a 5xx HTML page reads as the server-snag sentence", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("<html>502</html>", { status: 502 })));
    const err = await failure();
    expect(err.message).toBe(SERVER_ERROR_MESSAGE);
  });

  it("the API's bare 'Request failed.' 500 body becomes the server-snag sentence", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(500, { ok: false, error: "Request failed." })));
    expect((await failure()).message).toBe(SERVER_ERROR_MESSAGE);
  });

  it("a specific server error message is shown (the API writes `error`)", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(503, { ok: false, error: "Sleeper is temporarily unreachable. Wait a moment and try again.", reason: "provider_unavailable" })));
    const err = await failure();
    expect(err.message).toBe("Sleeper is temporarily unreachable. Wait a moment and try again.");
    expect(err.code).toBe("provider_unavailable");
  });

  it("a 403 without a message says what to do instead of a bare status", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(403, {})));
    expect((await failure()).message).toBe(FORBIDDEN_MESSAGE);
  });

  it("a dropped connection reads as offline", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    expect((await failure()).message).toBe(OFFLINE_ERROR_MESSAGE);
  });
});

describe("copy helpers", () => {
  it("friendlyStatusMessage", () => {
    expect(friendlyStatusMessage(401, "Invalid or expired session.")).toBe("Not signed in.");
    expect(friendlyStatusMessage(403, "")).toBe(FORBIDDEN_MESSAGE);
    expect(friendlyStatusMessage(403, "Not authorized.")).toBe("Not authorized.");
    expect(friendlyStatusMessage(500, "Request failed.")).toBe(SERVER_ERROR_MESSAGE);
  });
  it("isRetryableSessionLookupError", () => {
    expect(isRetryableSessionLookupError({ name: "AuthRetryableFetchError" })).toBe(true);
    expect(isRetryableSessionLookupError({ status: 502 })).toBe(true);
    expect(isRetryableSessionLookupError({ message: "Failed to fetch" })).toBe(true);
    expect(isRetryableSessionLookupError({ name: "AuthApiError", status: 400, message: "Invalid Refresh Token" })).toBe(false);
    expect(isRetryableSessionLookupError(null)).toBe(false);
  });
});

describe("forced sign-out detection", () => {
  it("only an unrequested SIGNED_OUT that ended a real session counts", () => {
    expect(isForcedSignOut({ event: "SIGNED_OUT", hadSession: true, userInitiated: false })).toBe(true);
    expect(isForcedSignOut({ event: "SIGNED_OUT", hadSession: true, userInitiated: true })).toBe(false);
    expect(isForcedSignOut({ event: "SIGNED_OUT", hadSession: false, userInitiated: false })).toBe(false);
    expect(isForcedSignOut({ event: "TOKEN_REFRESHED", hadSession: true, userInitiated: false })).toBe(false);
  });
  it("the marker expires and clears", () => {
    const store = new Map<string, string>();
    const storage = { setItem: (k: string, v: string) => void store.set(k, v), getItem: (k: string) => store.get(k) ?? null, removeItem: (k: string) => void store.delete(k) };
    markSessionEnded(storage, 1_000);
    expect(readSessionEnded(storage, 2_000)).toBe(true);
    expect(readSessionEnded(storage, 1_000 + 2 * 60 * 60 * 1000)).toBe(false);
    clearSessionEnded(storage);
    expect(readSessionEnded(storage, 2_000)).toBe(false);
  });
});
