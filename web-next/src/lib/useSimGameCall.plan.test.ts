import { renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { simGameGate } from "@/lib/simGame";
import { useSimGameCall } from "@/lib/useSimGameCall";

describe("plan verification", () => {
  it("classifies plan_unverified as retryable, never the paywall", () => {
    expect(simGameGate({ reason: "plan_unverified", is_premium: null, preview: null } as never)).toEqual({ kind: "unavailable", cause: "plan" });
  });

  it("retries once, then reports inline without a gate", async () => {
    const onGate = vi.fn();
    const onError = vi.fn();
    const { result } = renderHook(() => useSimGameCall(onGate, onError));
    const fn = vi.fn().mockResolvedValue({ reason: "plan_unverified", is_premium: null, preview: null });
    await expect(result.current(fn)).resolves.toBeNull();
    expect(fn).toHaveBeenCalledTimes(2);
    expect(onGate).not.toHaveBeenCalled();
    expect(onError).toHaveBeenCalledWith(expect.stringMatching(/verify your plan/));
  });

  it("tells the screen to clear a stale paywall once the server answers verified Pro", async () => {
    const onVerifiedPro = vi.fn();
    const { result } = renderHook(() => useSimGameCall(vi.fn(), vi.fn(), undefined, undefined, onVerifiedPro));
    await result.current(async () => ({ reason: "", is_premium: true, preview: null }));
    await result.current(async () => ({ reason: "", is_premium: false, preview: { paywalled: false, weeks_left: 3, paywall_week: 4 } }));
    expect(onVerifiedPro).toHaveBeenCalledTimes(1);
  });
});
