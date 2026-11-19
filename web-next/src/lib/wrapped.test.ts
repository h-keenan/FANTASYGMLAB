import { describe, expect, it } from "vitest";

import { normalizeWrappedDeck, wrappedGradeTone, wrappedShareModel, wrappedShareText, wrappedShortName, wrappedView, type WrappedCard } from "./wrapped";

const P = { id: "1", headshot_id: "1", name: "Marcus Hale", pos: "RB", team: "MIA" };
const card = (id: string, data: Record<string, unknown> | null, extra: Partial<WrappedCard> = {}): WrappedCard => ({ id, eyebrow: "E", title: "T", sub: null, pro: false, locked: false, data, ...extra });

describe("wrapped lib", () => {
  it("shortens names to J. Surname and keeps suffixes", () => {
    expect(wrappedShortName("Jalen Pruitt")).toBe("J. Pruitt");
    expect(wrappedShortName("Marvin Harrison Jr.")).toBe("M. Harrison Jr.");
    expect(wrappedShortName("Kyle")).toBe("Kyle");
    expect(wrappedShortName(null)).toBe("");
  });

  it("never colors a grade red", () => {
    for (const g of ["A", "B-", "C", "D", "F", "-"]) expect(["good", "warm", "neutral"]).toContain(wrappedGradeTone(g));
    expect(wrappedGradeTone("B+")).toBe("good");
  });

  it("parses a deck defensively and drops junk", () => {
    expect(normalizeWrappedDeck(null)).toBeNull();
    expect(normalizeWrappedDeck({ cards: [] })).toBeNull();
    const deck = normalizeWrappedDeck({ kind: "real", partial: true, season_label: "2026", team_name: "Comets", cards: [{ id: "intro", data: { record: "9-5" } }, { nope: 1 }] });
    expect(deck?.cards).toHaveLength(1);
    expect(deck?.kind).toBe("real");
  });

  it("bust card carries the why and a signed number", () => {
    const v = wrappedView(card("bust", { player: P, projected: 168, actual: 115.6, over_proj: -52.4, why: "Missed 5 games: hamstring" }));
    expect(v.kind).toBe("hero");
    if (v.kind === "hero") {
      expect(v.hero).toBe("-52.4");
      expect(v.rows.map((r) => r.value)).toEqual(["168.0", "115.6", "Missed 5 games: hamstring"]);
    }
  });

  it("a locked card has a teaser and no data", () => {
    const v = wrappedView(card("trades", null, { locked: true, pro: true }));
    expect(v).toEqual({ kind: "locked", teaser: expect.stringContaining("track record") });
  });

  it("builds share text with the team and season", () => {
    const model = wrappedShareModel(card("luck", { actual_wins: 9, expected_wins: 10.6, diff: -1.6, games: 14 }, { title: "You deserved better" }), { season_label: "Sim Season 1", team_name: "Lake City Comets" });
    const text = wrappedShareText(model);
    expect(text).toContain("You deserved better");
    expect(text).toContain("-1.6 wins vs expected");
    expect(text).toContain("Lake City Comets");
  });

  it("mvp over_proj is optional (real leagues have no projection)", () => {
    const v = wrappedView(card("mvp", { player: P, pts: 200, over_proj: null, ppg: 14.3, best: { week: null, pts: 30 }, share: 12 }));
    if (v.kind === "hero") expect(v.chip).toBeNull();
  });

  it("draft report cards: rounds, pick rows with a grade, value pair, summary", () => {
    const rounds = wrappedView(card("watch_draft", { grade: "B+", then: "B", rounds: [{ round: 1, actual: 214, expected: 198 }, { round: 2, actual: 163, expected: 171 }] }));
    expect(rounds.kind).toBe("rounds");
    if (rounds.kind === "rounds") expect(rounds.rows[0]).toMatchObject({ label: "Round 1", max: 214 });
    const busts = wrappedView(card("watch_busts", { rows: [{ player: P, text: "Rd 2, #17 · Missed 5 games: hamstring", grade: "D+", delta: -52.4 }] }));
    expect(busts.kind === "picks" && busts.rows[0]).toMatchObject({ grade: "D+", delta: "-52.4" });
    const stung = wrappedView(card("watch_whatif", { rows: [{ player: P, text: "Went right after G. Moreau", delta: 48, grade: null }] }));
    expect(stung.kind === "picks" && stung.rows[0].delta).toBe("+48 pts");
    const pair = wrappedView(card("watch_value", { steal: { player: P, text: "Round 5, pick 53 · finished RB14", delta: 38.9 }, reach: { player: P, text: "Round 4, pick 41 · finished WR48", delta: -31 } }));
    expect(pair.kind === "valuepair" && pair.items.map((i) => i.label)).toEqual(["The steal", "The reach"]);
    const summary = wrappedView(card("watch_standing", { grade: "B+", rows: [{ label: "Best pick", value: "O. Tillery", tone: "good" }] }));
    expect(summary.kind === "summary" && summary.rows[0].tone).toBe("good");
  });
});
