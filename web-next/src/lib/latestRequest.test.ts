import { describe, expect, it } from "vitest";

import { createLatestGate, createSingleFlight } from "./latestRequest";

function deferred<T>() {
  let resolve!: (v: T) => void;
  let reject!: (e: unknown) => void;
  const promise = new Promise<T>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  return { promise, resolve, reject };
}

describe("createLatestGate", () => {
  it("ignores league A's answer when B was requested later and answered first", async () => {
    const gate = createLatestGate(true);
    let shown = "";
    const a = deferred<string>();
    const b = deferred<string>();
    const load = (d: { promise: Promise<string> }) => {
      const current = gate.begin();
      return d.promise.then((v) => {
        if (current()) shown = v;
      });
    };
    const pa = load(a);
    const pb = load(b);
    b.resolve("B");
    await pb;
    a.resolve("A");
    await pa;
    expect(shown).toBe("B");
  });

  it("cancel retires an outstanding ticket", () => {
    const gate = createLatestGate(true);
    const current = gate.begin();
    gate.cancel();
    expect(current()).toBe(false);
  });

  it("kill switch off keeps every ticket current", () => {
    const gate = createLatestGate(false);
    const first = gate.begin();
    gate.begin();
    expect(first()).toBe(true);
  });
});

describe("createSingleFlight", () => {
  it("drops a second tap while the first is pending and allows one after it settles", async () => {
    const guard = createSingleFlight(true);
    const d = deferred<number>();
    let calls = 0;
    const first = guard.run(() => (calls++, d.promise));
    expect(guard.pending).toBe(true);
    expect(guard.run(() => (calls++, Promise.resolve(2)))).toBeUndefined();
    d.resolve(1);
    await first;
    expect(guard.pending).toBe(false);
    await guard.run(() => (calls++, Promise.resolve(3)));
    expect(calls).toBe(2);
  });

  it("clears the pending flag when the task rejects", async () => {
    const guard = createSingleFlight(true);
    await expect(guard.run(() => Promise.reject(new Error("x")))).rejects.toThrow("x");
    expect(guard.pending).toBe(false);
  });

  it("kill switch off lets every call through", () => {
    const guard = createSingleFlight(false);
    const d = deferred<number>();
    guard.run(() => d.promise);
    expect(guard.run(() => Promise.resolve(1))).toBeDefined();
  });
});
