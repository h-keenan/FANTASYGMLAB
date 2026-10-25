import { describe, expect, it } from "vitest";

import {
  RETURN_PATH_KEY,
  RETURN_PATH_TTL_MS,
  canConvertGuest,
  classifyEmailUpgradeResult,
  classifyUpgradeError,
  clearReturnPath,
  parseAuthCallbackError,
  readReturnPath,
  safeReturnPath,
  shouldRestoreReturnPath,
  storeReturnPath,
} from "./guestUpgrade";

function memStorage() {
  const m = new Map<string, string>();
  return {
    getItem: (k: string) => m.get(k) ?? null,
    setItem: (k: string, v: string) => void m.set(k, v),
    removeItem: (k: string) => void m.delete(k),
  };
}

describe("safeReturnPath", () => {
  it("accepts same-origin relative paths", () => {
    expect(safeReturnPath("/premium")).toBe("/premium");
    expect(safeReturnPath("/premium?plan=pro#x")).toBe("/premium?plan=pro#x");
  });
  it.each(["https://evil.com", "//evil.com", "/\\evil.com", "javascript:alert(1)", "premium", "", "/a\nb", "http:/evil"])(
    "rejects %j",
    (v) => expect(safeReturnPath(v)).toBeNull(),
  );
  it("rejects non-strings", () => {
    expect(safeReturnPath(null)).toBeNull();
    expect(safeReturnPath(undefined)).toBeNull();
  });
});

describe("canConvertGuest", () => {
  it("is true only for anonymous sessions", () => {
    expect(canConvertGuest({ user: { is_anonymous: true } })).toBe(true);
    expect(canConvertGuest({ user: { is_anonymous: false } })).toBe(false);
    expect(canConvertGuest(null)).toBe(false);
  });
});

describe("classifyUpgradeError", () => {
  it("detects the failure kinds", () => {
    expect(classifyUpgradeError({ code: "manual_linking_disabled" })).toBe("link-unavailable");
    expect(classifyUpgradeError({ message: "Manual linking is disabled" })).toBe("link-unavailable");
    expect(classifyUpgradeError({ code: "identity_already_exists" })).toBe("identity-exists");
    expect(classifyUpgradeError({ code: "email_exists" })).toBe("email-exists");
    expect(classifyUpgradeError({ message: "A user with this email address has already been registered" })).toBe("email-exists");
    expect(classifyUpgradeError({ code: "weak_password", message: "x" })).toBe("other");
    expect(classifyUpgradeError(null)).toBe("other");
  });
});

describe("classifyEmailUpgradeResult", () => {
  it("converted when permanent with the email set", () => {
    expect(classifyEmailUpgradeResult({ is_anonymous: false, email: "A@b.com" }, "a@b.com")).toBe("converted");
  });
  it("confirm-email while still anonymous", () => {
    expect(classifyEmailUpgradeResult({ is_anonymous: true, email: "" }, "a@b.com")).toBe("confirm-email");
    expect(classifyEmailUpgradeResult(null, "a@b.com")).toBe("confirm-email");
  });
});

describe("return path storage", () => {
  it("round trips and expires", () => {
    const s = memStorage();
    storeReturnPath(s, "/premium?x=1", 1000);
    expect(readReturnPath(s, 2000)).toBe("/premium?x=1");
    expect(readReturnPath(s, 1000 + RETURN_PATH_TTL_MS + 1)).toBeNull();
    clearReturnPath(s);
    expect(readReturnPath(s, 2000)).toBeNull();
  });
  it("never stores or returns unsafe paths", () => {
    const s = memStorage();
    storeReturnPath(s, "//evil.com", 1000);
    expect(s.getItem(RETURN_PATH_KEY)).toBeNull();
    s.setItem(RETURN_PATH_KEY, JSON.stringify({ path: "https://evil.com", at: 1000 }));
    expect(readReturnPath(s, 1500)).toBeNull();
    s.setItem(RETURN_PATH_KEY, "not json");
    expect(readReturnPath(s, 1500)).toBeNull();
  });
});

describe("parseAuthCallbackError", () => {
  it("reads query or hash errors", () => {
    expect(parseAuthCallbackError("", "#error=server_error&error_code=identity_already_exists&error_description=Identity+is+already+linked")).toEqual({
      code: "identity_already_exists",
      description: "Identity is already linked",
    });
    expect(parseAuthCallbackError("?error_code=manual_linking_disabled", "")?.code).toBe("manual_linking_disabled");
    expect(parseAuthCallbackError("?a=1", "")).toBeNull();
  });
});

describe("shouldRestoreReturnPath", () => {
  const base = { stored: "/premium", isAnonymous: false, hasSession: true, currentPath: "/" };
  it("fires for a real session away from the path", () => {
    expect(shouldRestoreReturnPath(base)).toBe(true);
  });
  it("does not fire for guests, no session, no stored path, or same path", () => {
    expect(shouldRestoreReturnPath({ ...base, isAnonymous: true })).toBe(false);
    expect(shouldRestoreReturnPath({ ...base, hasSession: false })).toBe(false);
    expect(shouldRestoreReturnPath({ ...base, stored: null })).toBe(false);
    expect(shouldRestoreReturnPath({ ...base, currentPath: "/premium" })).toBe(false);
  });
});
