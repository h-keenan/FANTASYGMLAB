import { renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { useSimGameCall } from "@/lib/useSimGameCall";

describe("useSimGameCall", () => {
  function setup() {
    const onGate = vi.fn();
    const onError = vi.fn();
    const hook = renderHook(() => useSimGameCall(onGate, onError));
    return { call: hook.result.current, onGate, onError };
  }

  it("retries a storage failure once on its own and then succeeds without a gate", async () => {
    const { call, onGate, onError } = setup();
    const fn = vi.fn().mockResolvedValueOnce({ reason: "sim_storage_unavailable", detail: "http_5xx" }).mockResolvedValueOnce({ reason: "" });
    await expect(call(fn)).resolves.toEqual({ reason: "" });
    expect(fn).toHaveBeenCalledTimes(2);
    expect(onGate).not.toHaveBeenCalled();
    expect(onError).not.toHaveBeenCalled();
  });

  it("reports a persistent storage failure inline with its detail code, never as a full-screen gate", async () => {
    const { call, onGate, onError } = setup();
    const fn = vi.fn().mockResolvedValue({ reason: "sim_storage_unavailable", detail: "constraint" });
    await expect(call(fn)).resolves.toBeNull();
    expect(onGate).not.toHaveBeenCalled();
    expect(onError).toHaveBeenCalledWith(expect.stringMatching(/Couldn't save that.*\(constraint\)/));
  });

  it("keeps the flag-off gate and does not retry it", async () => {
    const { call, onGate } = setup();
    const fn = vi.fn().mockRejectedValue({ status: 404 });
    await expect(call(fn)).resolves.toBeNull();
    expect(fn).toHaveBeenCalledTimes(1);
    expect(onGate).toHaveBeenCalledWith({ kind: "unavailable", cause: "off" });
  });

  it("retries a raced write (409) once silently so one tap applies; a second conflict still reports", async () => {
    const { call, onGate } = setup();
    const ok = vi.fn().mockRejectedValueOnce({ status: 409 }).mockResolvedValueOnce({ reason: "", executed: true });
    await expect(call(ok)).resolves.toEqual({ reason: "", executed: true });
    expect(ok).toHaveBeenCalledTimes(2);
    expect(onGate).not.toHaveBeenCalled();
    const bad = vi.fn().mockRejectedValue({ status: 409 });
    await expect(call(bad)).resolves.toBeNull();
    expect(bad).toHaveBeenCalledTimes(2);
    expect(onGate).toHaveBeenCalledWith({ kind: "conflict" });
  });
});
