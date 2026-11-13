import { describe, expect, it } from "vitest";

import { createMemoryTabStore, readSavedTab, resolveTab, saveTab, tabDirection } from "./sessionTab";

describe("session tab helpers", () => {
  it("resolves remembered, then initial, then first", () => {
    expect(resolveTab("stats", ["a", "stats"], "a")).toBe("stats");
    expect(resolveTab("gone", ["a", "b"], "b")).toBe("b");
    expect(resolveTab(null, ["a", "b"], "zzz")).toBe("a");
    expect(resolveTab(null, [], undefined)).toBe("");
  });
  it("slides toward the picked tab", () => {
    expect(tabDirection(["a", "b", "c"], "a", "c")).toBe(1);
    expect(tabDirection(["a", "b", "c"], "c", "b")).toBe(-1);
    expect(tabDirection(["a", "b"], "a", "a")).toBe(0);
    expect(tabDirection(["a", "b"], "x", "b")).toBe(0);
  });
  it("round-trips through a store and shrugs off a throwing one", () => {
    const store = createMemoryTabStore();
    saveTab(store, "pqv", "history");
    expect(readSavedTab(store, "pqv")).toBe("history");
    expect(readSavedTab(store, "other")).toBeNull();
    const bad = { getItem: () => { throw new Error("x"); }, setItem: () => { throw new Error("x"); } };
    expect(readSavedTab(bad, "pqv")).toBeNull();
    expect(() => saveTab(bad, "pqv", "a")).not.toThrow();
    expect(readSavedTab(null, "pqv")).toBeNull();
  });
});
