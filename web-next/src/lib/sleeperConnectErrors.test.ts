import { describe, expect, it } from "vitest";

import { describeSleeperConnectError, isConnectivityFailure } from "./sleeperConnectErrors";

describe("describeSleeperConnectError", () => {
  it("explains user_not_found with the username hint, offering the sample", () => {
    const e = describeSleeperConnectError({ status: "user_not_found", username: "bob" });
    expect(e.kind).toBe("user_not_found");
    expect(e.message).toContain('"bob"');
    expect(e.hint).toMatch(/not your display name or email/);
    expect(e.offerSample).toBe(true);
    expect(e.offerSleeperSignup).toBe(true);
  });
  it("explains no_leagues and offers the sample", () => {
    const e = describeSleeperConnectError({ status: "no_leagues", username: "bob" });
    expect(e.kind).toBe("no_leagues");
    expect(e.hint).toMatch(/this season and last season/);
    expect(e.offerSample).toBe(true);
  });
  it("treats unavailable/network as a retry message", () => {
    expect(describeSleeperConnectError({ status: "unavailable" }).kind).toBe("network");
    expect(describeSleeperConnectError({ status: "network" }).hint).toMatch(/try again/);
  });
  it("falls back to the server message", () => {
    expect(describeSleeperConnectError({ status: "x", serverMessage: "Boom" }).message).toBe("Boom");
  });
});

describe("isConnectivityFailure", () => {
  it("is true for status 0, 5xx and bare errors; false for 4xx", () => {
    expect(isConnectivityFailure({ status: 0 })).toBe(true);
    expect(isConnectivityFailure({ status: 503 })).toBe(true);
    expect(isConnectivityFailure(new TypeError("Network request failed"))).toBe(true);
    expect(isConnectivityFailure({ status: 400 })).toBe(false);
  });
});
