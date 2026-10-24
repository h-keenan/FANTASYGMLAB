import { afterEach, describe, expect, it, vi } from "vitest";
import { timeoutSignal } from "@/lib/shareCard/clientRender";

afterEach(() => {
  vi.useRealTimers();
});

describe("timeoutSignal", () => {
  it("works when AbortSignal.timeout is missing (older iOS Safari)", () => {
    vi.useFakeTimers();
    const original = AbortSignal.timeout;
    // @ts-expect-error simulate old Safari
    delete AbortSignal.timeout;
    try {
      const { signal, clear } = timeoutSignal(100);
      expect(signal?.aborted).toBe(false);
      vi.advanceTimersByTime(101);
      expect(signal?.aborted).toBe(true);
      clear();
    } finally {
      AbortSignal.timeout = original;
    }
  });

  it("clear() prevents the abort", () => {
    vi.useFakeTimers();
    const { signal, clear } = timeoutSignal(100);
    clear();
    vi.advanceTimersByTime(200);
    expect(signal?.aborted).toBe(false);
  });
});
