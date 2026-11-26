import { describe, expect, it } from "vitest";

import { detectAccountEvent, signupMethodOf, type MarkerStorage } from "./signupTracking";

function store(): MarkerStorage {
  const m = new Map<string, string>();
  return {
    getItem: (k) => m.get(k) ?? null,
    setItem: (k, v) => void m.set(k, v),
    removeItem: (k) => void m.delete(k),
  };
}
const NOW = Date.parse("2026-11-26T12:00:00Z");
const iso = (minAgo: number) => new Date(NOW - minAgo * 60_000).toISOString();

describe("signupMethodOf", () => {
  it("reads identities, then app_metadata", () => {
    expect(signupMethodOf({ identities: [{ provider: "google" }] })).toBe("google");
    expect(signupMethodOf({ app_metadata: { provider: "apple" } })).toBe("apple");
    expect(signupMethodOf({ app_metadata: { provider: "email" } })).toBe("email");
    expect(signupMethodOf({ app_metadata: { provider: "github" } })).toBe("other");
  });
});

describe("detectAccountEvent", () => {
  it("reports a brand-new Google/Apple/email account once", () => {
    const s = store();
    for (const provider of ["google", "apple", "email"]) {
      const user = { id: `u-${provider}`, created_at: iso(1), app_metadata: { provider } };
      expect(detectAccountEvent(user, s, NOW)).toEqual({ kind: "signup", event: "signup_completed", method: provider });
      expect(detectAccountEvent(user, s, NOW)).toBeNull(); // deduped
    }
  });

  it("does not count an old account signing in again", () => {
    expect(detectAccountEvent({ id: "u1", created_at: iso(60 * 24 * 30), app_metadata: { provider: "google" } }, store(), NOW)).toBeNull();
  });

  it("counts an email account when the confirmation link is clicked later", () => {
    const user = { id: "u2", created_at: iso(300), email_confirmed_at: iso(2), app_metadata: { provider: "email" } };
    expect(detectAccountEvent(user, store(), NOW)?.event).toBe("signup_completed");
  });

  it("reports a new guest once, then signup_completed when that guest is upgraded", () => {
    const s = store();
    const guest = { id: "g1", is_anonymous: true, created_at: iso(1) };
    expect(detectAccountEvent(guest, s, NOW)).toEqual({ kind: "guest", event: "guest_session_started" });
    expect(detectAccountEvent(guest, s, NOW)).toBeNull();
    const upgraded = { id: "g1", created_at: iso(120), identities: [{ provider: "apple" }] };
    expect(detectAccountEvent(upgraded, s, NOW)).toEqual({ kind: "signup", event: "signup_completed", method: "apple" });
    expect(detectAccountEvent(upgraded, s, NOW)).toBeNull();
  });

  it("is a no-op without a user or storage", () => {
    expect(detectAccountEvent(null, store(), NOW)).toBeNull();
    expect(detectAccountEvent({ id: "x", created_at: iso(1) }, null, NOW)).toBeNull();
  });
});
