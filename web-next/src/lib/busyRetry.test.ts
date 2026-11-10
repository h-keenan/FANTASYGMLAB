import { describe, expect, it, vi } from "vitest";
import {
  MAX_BUSY_RETRIES,
  MAX_BUSY_WAIT_MS,
  busyDelayMs,
  isServerBusyError,
  parseRetryAfterSeconds,
  withServerBusyRetry,
} from "./busyRetry";

const busy = (retryAfterSeconds?: number) => ({ status: 503, code: "server_busy", retryAfterSeconds });

describe("busyRetry", () => {
  it("recognizes only 503 server_busy", () => {
    expect(isServerBusyError(busy(3))).toBe(true);
    expect(isServerBusyError({ status: 503 })).toBe(false);
    expect(isServerBusyError({ status: 429, code: "server_busy" })).toBe(false);
    expect(isServerBusyError(null)).toBe(false);
  });

  it("parses Retry-After seconds", () => {
    expect(parseRetryAfterSeconds("5")).toBe(5);
    expect(parseRetryAfterSeconds("2.2")).toBe(3);
    expect(parseRetryAfterSeconds("")).toBeUndefined();
    expect(parseRetryAfterSeconds("Wed, 21 Oct 2026 07:28:00 GMT")).toBeUndefined();
    expect(parseRetryAfterSeconds("0")).toBeUndefined();
  });

  it("honors the hint, jitters upward, and is capped", () => {
    expect(busyDelayMs(4, 0, () => 0)).toBe(4000);
    expect(busyDelayMs(4, 0, () => 1)).toBe(4800);
    expect(busyDelayMs(undefined, 1, () => 0)).toBe(4000);
    expect(busyDelayMs(60, 0, () => 0)).toBe(MAX_BUSY_WAIT_MS);
  });

  it("retries a busy GET and returns the eventual success", async () => {
    const run = vi.fn().mockRejectedValueOnce(busy(2)).mockResolvedValueOnce("ok");
    const sleep = vi.fn().mockResolvedValue(undefined);
    await expect(withServerBusyRetry(run, { canRetry: true, sleep, random: () => 0 })).resolves.toBe("ok");
    expect(run).toHaveBeenCalledTimes(2);
    expect(sleep).toHaveBeenCalledWith(2000, undefined);
  });

  it("gives up after the retry budget and surfaces the busy error", async () => {
    const err = busy(1);
    const run = vi.fn().mockRejectedValue(err);
    const sleep = vi.fn().mockResolvedValue(undefined);
    await expect(withServerBusyRetry(run, { canRetry: true, sleep })).rejects.toBe(err);
    expect(run).toHaveBeenCalledTimes(MAX_BUSY_RETRIES + 1);
  });

  it("never retries writes or non-busy errors", async () => {
    const sleep = vi.fn();
    const write = vi.fn().mockRejectedValue(busy(1));
    await expect(withServerBusyRetry(write, { canRetry: false, sleep })).rejects.toBeTruthy();
    expect(write).toHaveBeenCalledTimes(1);
    const other = vi.fn().mockRejectedValue({ status: 500 });
    await expect(withServerBusyRetry(other, { canRetry: true, sleep })).rejects.toBeTruthy();
    expect(other).toHaveBeenCalledTimes(1);
    expect(sleep).not.toHaveBeenCalled();
  });

  it("stops retrying once the caller aborted", async () => {
    const controller = new AbortController();
    controller.abort();
    const run = vi.fn().mockRejectedValue(busy(1));
    await expect(withServerBusyRetry(run, { canRetry: true, signal: controller.signal, sleep: vi.fn() })).rejects.toBeTruthy();
    expect(run).toHaveBeenCalledTimes(1);
  });
});
