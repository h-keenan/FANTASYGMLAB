import { afterEach, describe, expect, it, vi } from "vitest";

import { fetchTryExamples, parseTryExamples, realStartSitMatchup, realWaiversResponse } from "./tryExamples";
import { REAL_PAYLOAD } from "./tryExamples.fixture";

describe("parseTryExamples", () => {
  it("accepts the real payload and builds the shapes the real modules read", () => {
    const ex = parseTryExamples(REAL_PAYLOAD)!;
    expect(ex.week).toBe(12);
    expect(realStartSitMatchup(ex.startSit!).suggested_moves?.[0].start.name).toBe("Real Alpha");
    const w = realWaiversResponse(ex.waivers!);
    expect(w.priority_adds[0]).toMatchObject({ name: "Wire Echo", injury_cover_for: "Hurt Golf" });
    expect(w.priority_adds[0].faab).toMatchObject({ low_bid: 6, high_bid: 11 });
    expect(w.priority_adds[0].recommendation_reason).toContain("5,400 adds");
  });

  it("is deterministic for the same payload", () => {
    expect(JSON.stringify(parseTryExamples(REAL_PAYLOAD))).toBe(JSON.stringify(parseTryExamples(REAL_PAYLOAD)));
  });

  it("returns null sections (the sample-league fallback) for the offseason payload, never invented ones", () => {
    const ex = parseTryExamples({ ok: true, season: 2026, week: null, start_sit: null, waivers: null, unavailable_reason: "offseason" })!;
    expect(ex.startSit).toBeNull();
    expect(ex.waivers).toBeNull();
  });

  it("drops malformed sections and rejects non-payloads", () => {
    const bad = { ...REAL_PAYLOAD, start_sit: { move: { start: {}, over: {}, gain: 1 }, matchup_note: "x" }, waivers: { adds: [{ name: "No id" }] } };
    const ex = parseTryExamples(bad)!;
    expect(ex.startSit).toBeNull();
    expect(ex.waivers).toBeNull();
    expect(parseTryExamples(null)).toBeNull();
    expect(parseTryExamples({ ok: false })).toBeNull();
  });
});

describe("fetchTryExamples", () => {
  afterEach(() => vi.restoreAllMocks());

  it("returns null on a transport failure so the page falls back", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("down"));
    expect(await fetchTryExamples()).toBeNull();
  });

  it("returns parsed examples on success", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(new Response(JSON.stringify(REAL_PAYLOAD), { status: 200 }));
    expect((await fetchTryExamples())?.startSit?.move.start.name).toBe("Real Alpha");
  });
});
