import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const realGetSession = vi.fn();
const realOnAuthStateChange = vi.fn();
const realSignOut = vi.fn();
const authModuleLoaded = vi.fn();

vi.mock("./env", () => ({ env: { supabaseUrl: "https://abcdefgh.supabase.co", supabaseAnonKey: "anon", apiBaseUrl: "" } }));
vi.mock("./supabaseAuth", () => {
  authModuleLoaded();
  return {
    auth: { getSession: realGetSession, onAuthStateChange: realOnAuthStateChange, signOut: realSignOut },
  };
});

const KEY = "sb-abcdefgh-auth-token";

function stored(overrides: Record<string, unknown> = {}) {
  return {
    access_token: "tok",
    refresh_token: "r",
    token_type: "bearer",
    expires_in: 3600,
    expires_at: Math.floor(Date.now() / 1000) + 3000,
    user: { id: "u1" },
    ...overrides,
  };
}

async function freshModule() {
  vi.resetModules();
  authModuleLoaded.mockClear();
  return import("./supabase");
}

describe("supabase auth facade", () => {
  beforeEach(() => {
    window.localStorage.clear();
    window.history.replaceState(null, "", "/");
    realGetSession.mockReset().mockResolvedValue({ data: { session: { access_token: "real" } }, error: null });
    realOnAuthStateChange.mockReset().mockReturnValue({ data: { subscription: { unsubscribe: vi.fn() } } });
    realSignOut.mockReset().mockResolvedValue({ error: null });
  });
  afterEach(() => {
    window.localStorage.clear();
  });

  it("answers getSession from a healthy stored session without loading the auth client", async () => {
    window.localStorage.setItem(KEY, JSON.stringify(stored()));
    const { supabase } = await freshModule();
    const { data } = await supabase.auth.getSession();
    expect(data.session?.access_token).toBe("tok");
    expect(realGetSession).not.toHaveBeenCalled();
  });

  it("goes through the real client when nothing is stored", async () => {
    const { supabase } = await freshModule();
    const { data } = await supabase.auth.getSession();
    expect(data.session?.access_token).toBe("real");
  });

  it("does not trust an expired or nearly expired stored token (the real client refreshes it)", async () => {
    window.localStorage.setItem(KEY, JSON.stringify(stored({ expires_at: Math.floor(Date.now() / 1000) + 30 })));
    const { supabase } = await freshModule();
    const { data } = await supabase.auth.getSession();
    expect(data.session?.access_token).toBe("real");
  });

  it("ignores malformed storage", async () => {
    window.localStorage.setItem(KEY, "{not json");
    const { peekStoredSession } = await freshModule();
    expect(peekStoredSession()).toBeNull();
    window.localStorage.setItem(KEY, JSON.stringify({ access_token: "x" }));
    expect(peekStoredSession()).toBeNull();
  });

  it("lets the real client parse an auth callback URL instead of using the stored session", async () => {
    window.localStorage.setItem(KEY, JSON.stringify(stored()));
    window.history.replaceState(null, "", "/#access_token=abc&type=recovery");
    const { supabase } = await freshModule();
    const { data } = await supabase.auth.getSession();
    expect(data.session?.access_token).toBe("real");
  });

  it("delegates everything to the real client once it has loaded", async () => {
    window.localStorage.setItem(KEY, JSON.stringify(stored()));
    const { supabase } = await freshModule();
    await supabase.auth.signOut();
    expect(realSignOut).toHaveBeenCalledTimes(1);
    const { data } = await supabase.auth.getSession();
    expect(data.session?.access_token).toBe("real");
  });

  it("subscribes the auth listener as soon as something else loads the client (no missed sign-in event)", async () => {
    const { supabase } = await freshModule();
    const callback = vi.fn();
    const { data } = supabase.auth.onAuthStateChange(callback);
    expect(realOnAuthStateChange).not.toHaveBeenCalled();
    await supabase.auth.signOut();
    await Promise.resolve();
    expect(realOnAuthStateChange).toHaveBeenCalledWith(callback);
    data.subscription.unsubscribe();
  });

  it("an unsubscribe before the client loads means the listener is never attached", async () => {
    const { supabase } = await freshModule();
    const { data } = supabase.auth.onAuthStateChange(vi.fn());
    data.subscription.unsubscribe();
    await supabase.auth.signOut();
    await Promise.resolve();
    expect(realOnAuthStateChange).not.toHaveBeenCalled();
  });
});
