import { describe, expect, it } from "vitest";

import { isBillingReturn } from "@/components/LandingAuthIsland";

describe("isBillingReturn", () => {
  it("treats both the hosted (success) and embedded (complete) return values as a finished checkout", () => {
    expect(isBillingReturn("success")).toBe(true);
    expect(isBillingReturn("complete")).toBe(true);
  });

  it("ignores cancel, empty and unknown values so onboarding still runs", () => {
    expect(isBillingReturn("cancel")).toBe(false);
    expect(isBillingReturn("")).toBe(false);
    expect(isBillingReturn(null)).toBe(false);
    expect(isBillingReturn("yes")).toBe(false);
  });
});
