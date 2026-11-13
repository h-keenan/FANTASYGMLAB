import { describe, expect, it } from "vitest";
import { dataAgeSeconds, freshnessLabel, nextPollDelayMs, projFinalLabel, shouldPoll } from "./liveScores";

const noJitter = () => 0;

describe("liveScores", () => {
  it("polls only when live, visible and online", () => {
    expect(shouldPoll({ live: true, visible: true, online: true })).toBe(true);
    expect(shouldPoll({ live: false, visible: true, online: true })).toBe(false);
    expect(shouldPoll({ live: true, visible: false, online: true })).toBe(false);
    expect(shouldPoll({ live: true, visible: true, online: false })).toBe(false);
  });
  it("clamps the server interval to 30-120s", () => {
    expect(nextPollDelayMs(10, 0, undefined, noJitter)).toBe(30_000);
    expect(nextPollDelayMs(30, 0, undefined, noJitter)).toBe(30_000);
    expect(nextPollDelayMs(75, 0, undefined, noJitter)).toBe(75_000);
    expect(nextPollDelayMs(500, 0, undefined, noJitter)).toBe(120_000);
    expect(nextPollDelayMs(null, 0, undefined, noJitter)).toBe(30_000);
  });
  it("backs off exponentially on errors, capped, honoring Retry-After", () => {
    expect(nextPollDelayMs(30, 1, undefined, noJitter)).toBe(60_000);
    expect(nextPollDelayMs(30, 2, undefined, noJitter)).toBe(120_000);
    expect(nextPollDelayMs(30, 9, undefined, noJitter)).toBe(300_000);
    expect(nextPollDelayMs(30, 0, 90, noJitter)).toBe(90_000);
  });
  it("worst-case lag while live stays under 60s of cache + one poll", () => {
    const serverTtl = 20;
    expect(serverTtl + nextPollDelayMs(30, 0, undefined, noJitter) / 1000).toBeLessThanOrEqual(60);
  });
  it("labels freshness", () => {
    expect(freshnessLabel(2)).toBe("Updated just now");
    expect(freshnessLabel(12)).toBe("Updated 12s ago");
    expect(freshnessLabel(190)).toBe("Updated 3m ago");
    expect(dataAgeSeconds(8, 1_000, 5_000)).toBe(12);
  });
  it("formats projected final", () => {
    expect(projFinalLabel(18.44)).toBe("Proj final 18.4");
    expect(projFinalLabel(null)).toBeNull();
  });
});
