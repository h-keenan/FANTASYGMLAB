import { describe, expect, it } from "vitest";

import { parseYahooReturn, yahooNeedsConnect, yahooReasonMessage } from "./yahooConnect";

describe("yahooConnect", () => {
  it("reads the web return query", () => {
    expect(parseYahooReturn("?yahoo=connected")).toEqual({ connected: true, reason: "" });
    expect(parseYahooReturn("?yahoo=error&yahoo_reason=denied")).toEqual({ connected: false, reason: "denied" });
  });

  it("reads the app deep link", () => {
    expect(parseYahooReturn("fantasygmlab://yahoo?status=connected")).toEqual({ connected: true, reason: "" });
    expect(parseYahooReturn("fantasygmlab://yahoo?status=error&reason=storage_failed")).toEqual({ connected: false, reason: "storage_failed" });
    expect(parseYahooReturn("fantasygmlab://yahoo?status=error")).toEqual({ connected: false, reason: "exchange_failed" });
  });

  it("ignores anything that is not a Yahoo return", () => {
    expect(parseYahooReturn("")).toBeNull();
    expect(parseYahooReturn(null)).toBeNull();
    expect(parseYahooReturn("?name=Sunday")).toBeNull();
    expect(parseYahooReturn("?status=pending")).toBeNull();
  });

  it("prefers the server message and falls back to reason copy", () => {
    expect(yahooReasonMessage("denied", "Custom")).toBe("Custom");
    expect(yahooReasonMessage("reconnect_needed")).toContain("Connect Yahoo");
    expect(yahooReasonMessage("zzz")).toContain("Something went wrong");
  });

  it("knows which reasons need a fresh sign-in", () => {
    expect(yahooNeedsConnect("reconnect_needed")).toBe(true);
    expect(yahooNeedsConnect("not_connected")).toBe(true);
    expect(yahooNeedsConnect("yahoo_unavailable")).toBe(false);
  });
});
