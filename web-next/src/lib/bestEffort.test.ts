import { beforeEach, describe, expect, it, vi } from "vitest";


const report = vi.hoisted(() => vi.fn());
vi.mock("@/lib/errorReporter", () => ({ reportError: report }));

describe("bestEffort", () => {
  let bestEffort: typeof import("@/lib/bestEffort").bestEffort;
  beforeEach(async () => {
    report.mockClear();
    vi.resetModules();
    ({ bestEffort } = await import("@/lib/bestEffort"));
  });

  it("reports a failed optional read once per label, with the label as context", () => {
    const handler = bestEffort("manager_tendencies");
    handler(new Error("a"));
    handler(new Error("b"));
    bestEffort("player_value_history")(new Error("c"));
    expect(report).toHaveBeenCalledTimes(2);
    expect(report.mock.calls[0][1]).toEqual({ best_effort: "manager_tendencies" });
  });

  it("never throws", async () => {
    await expect(Promise.reject(new Error("x")).catch(bestEffort("x"))).resolves.toBeUndefined();
  });
});
