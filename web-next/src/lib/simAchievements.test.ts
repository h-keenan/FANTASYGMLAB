import { describe, expect, it } from "vitest";

import {
  simAchievementColor,
  simAchievementDate,
  simAchievementGlyph,
  simAchievementGroups,
  simAchievementProgressPct,
  simAchievementsParts,
  simAttachAchievements,
  simPlayerBadges,
  simRecapAchievementModel,
  simRecapHasAchievements,
  simTeamTrophies,
  type SimAchievement,
  type SimMilestoneBanner,
} from "./simAchievements";
import { simRecapPageKeys, simRecapPageTitle } from "./simRecapStory";
import type { SimWeekRecap } from "./simGame";

const ach = (over: Partial<SimAchievement> = {}): SimAchievement => ({
  id: "x:1", key: "x", scope: "season", rarity: "common", tone: "good", icon: "check", name: "X", detail: "d", unlocked: true,
  season_no: 1, year: 2026, season_label: "S1 2026", week: 5, at: 105, progress: null, tier: null, player: null, ...over,
});
const banner = (over: Partial<SimMilestoneBanner> = {}): SimMilestoneBanner => ({ kind: "perfect_run", tone: "good", icon: "flame", confetti: false, headline: "WIN #10, still perfect", sub: "10-0", ...over });

describe("colours", () => {
  it("is gold only for epic good badges, never for bad luck, muted when locked", () => {
    expect(simAchievementColor(ach({ rarity: "epic" }))).toBe("var(--color-premium)");
    expect(simAchievementColor(ach({ rarity: "epic", tone: "bad" }))).toBe("var(--color-danger)");
    expect(simAchievementColor(ach({ rarity: "rare" }))).toBe("var(--color-accent)");
    expect(simAchievementColor(ach({ rarity: "common" }))).toBe("var(--color-success)");
    expect(simAchievementColor(ach({ rarity: "epic", unlocked: false }))).toBe("var(--color-text-muted)");
    for (const rarity of ["common", "rare"] as const) expect(simAchievementColor(ach({ rarity }))).not.toBe("var(--color-premium)");
  });
  it("maps every server icon to a glyph", () => {
    for (const icon of ["trophy", "crown", "flame", "snow", "bolt", "shield", "target", "heart", "rocket", "fall", "star", "swap", "wand", "check", "calendar", "unknown"]) {
      expect(typeof simAchievementGlyph(icon)).toBe("string");
    }
    expect(simAchievementGlyph("crown")).toBe("trophy");
  });
});

describe("dates and progress", () => {
  it("uses the shared season label and week", () => {
    expect(simAchievementDate(ach({ season_label: "S3 2028", week: 14 }))).toBe("S3 2028 · Wk 14");
    expect(simAchievementDate(ach({ season_label: "", week: 4 }))).toBe("Wk 4");
    expect(simAchievementDate(ach({ season_label: "S2 2027", week: null }))).toBe("S2 2027");
    expect(simAchievementDate(ach({ unlocked: false }))).toBe("");
  });
  it("clamps the progress bar", () => {
    expect(simAchievementProgressPct({ current: 11, target: 14, text: "" })).toBe(79);
    expect(simAchievementProgressPct({ current: 20, target: 14, text: "" })).toBe(100);
    expect(simAchievementProgressPct(null)).toBe(0);
    expect(simAchievementProgressPct({ current: 1, target: 0, text: "" })).toBe(0);
  });
});

describe("module", () => {
  const items = [
    ach({ id: "a:1", season_no: 1, at: 114, name: "Old", season_label: "S1 2026" }),
    ach({ id: "a:2", season_no: 2, at: 205, name: "New", season_label: "S2 2027" }),
    ach({ id: "career_wins_10", scope: "career", at: 205, name: "10 Career Wins" }),
    ach({ id: "perfect_season:2", unlocked: false, name: "Perfect Season", progress: { current: 11, target: 14, text: "11-0, 3 games left" }, at: null, week: null }),
    ach({ id: "career_wins_25", scope: "career", unlocked: false, name: "25 Career Wins", progress: { current: 10, target: 25, text: "10 of 25 wins" }, at: null, week: null }),
  ];
  it("groups this season, earlier seasons, career and locked, dropping empty groups", () => {
    const groups = simAchievementGroups({ items }, 2);
    expect(groups.map((g) => g.title)).toEqual(["This season", "Earlier seasons", "Career", "Still to earn"]);
    expect(groups[0].items.map((a) => a.name)).toEqual(["New"]);
    expect(groups[3].items[0].name).toBe("Perfect Season"); // closest to done first
    expect(simAchievementGroups({ items: [] }, 1)).toEqual([]);
    expect(simAchievementGroups(null)).toEqual([]);
  });
  it("summarises in one collapsed line with the next target", () => {
    const parts = simAchievementsParts({ items });
    expect(parts.map((p) => p.text)).toEqual(["3 unlocked", "next: Perfect Season (11-0, 3 games left)"]);
    expect(simAchievementsParts({ items: [] })[0].text).toMatch(/Play a week/);
    expect(simAchievementsParts({ items: [ach({ rarity: "epic" })] }).map((p) => p.text)).toEqual(["1 unlocked", "1 epic", "latest: X"]);
  });
});

describe("recap banner", () => {
  it("is empty without badges or milestones", () => {
    expect(simRecapAchievementModel(null)).toBeNull();
    expect(simRecapAchievementModel({ new: [], milestones: [] })).toBeNull();
    expect(simRecapHasAchievements({ new: [], milestones: [] })).toBe(false);
  });
  it("celebrates a perfect season with confetti and a trophy, and drops the redundant milestone", () => {
    const m = simRecapAchievementModel({ new: [ach({ key: "champion", rarity: "rare", name: "League Champion" }), ach({ id: "p:1", key: "perfect_season", rarity: "epic", name: "Perfect Season", detail: "14-0 and the title" })], milestones: [banner()] })!;
    expect(m.headline).toBe("Perfect Season");
    expect(m).toMatchObject({ tone: "premium", celebrate: true, trophy: true, banners: [] });
    expect(m.items.map((a) => a.key)).toEqual(["perfect_season", "champion"]);
  });
  it("is sympathetic, never gold and never confetti, for a winless season", () => {
    const yes = simRecapAchievementModel({ new: [ach({ key: "winless", tone: "bad", rarity: "rare", name: "Winless Season", detail: "0-14: not a single win. The #1 pick is yours." })], milestones: [] })!;
    expect(yes).toMatchObject({ headline: "Winless... the #1 pick is yours", tone: "danger", celebrate: false, trophy: false });
    expect(yes.sub).not.toMatch(/#1 pick is yours/);
    const no = simRecapAchievementModel({ new: [ach({ key: "winless", tone: "bad", name: "Winless Season", detail: "0-14: not a single win." })], milestones: [] })!;
    expect(no.headline).toBe("Winless... it happens to the best of us");
  });
  it("falls back to the milestone banner when nothing unlocked", () => {
    const m = simRecapAchievementModel({ new: [], milestones: [banner(), banner({ kind: "win_number", headline: "WIN #10" })] })!;
    expect(m).toMatchObject({ headline: "WIN #10, still perfect", eyebrow: "Milestone", celebrate: false, items: [] });
    expect(m.banners).toHaveLength(1);
    expect(simRecapAchievementModel({ new: [], milestones: [banner({ tone: "bad", kind: "winless_watch", headline: "Still hunting win #1 (0-5)" })] })!.tone).toBe("danger");
  });
  it("tones a bad-luck badge warning, an epic good one premium, a rare accent", () => {
    expect(simRecapAchievementModel({ new: [ach({ key: "heartbreaker", tone: "bad", rarity: "rare" })], milestones: [] })!.tone).toBe("warning");
    expect(simRecapAchievementModel({ new: [ach({ key: "blowout", rarity: "rare" })], milestones: [] })!.tone).toBe("accent");
    expect(simRecapAchievementModel({ new: [ach({ key: "blowout", rarity: "common" })], milestones: [] })!.tone).toBe("success");
  });
});

describe("attaching to the played weeks", () => {
  const recaps = [{ week: 14 }, { week: 15 }, { week: 16 }];
  it("gives every badge to its own week and the banners to the first", () => {
    const out = simAttachAchievements(recaps, { items: [], new: [ach({ id: "a", week: 14 }), ach({ id: "b", week: 16 })], milestones: [banner()] });
    expect(out[0].achievements?.new.map((a) => a.id)).toEqual(["a"]);
    expect(out[0].achievements?.milestones).toHaveLength(1);
    expect(out[1].achievements).toBeUndefined();
    expect(out[2].achievements?.new.map((a) => a.id)).toEqual(["b"]);
  });
  it("leaves the recaps alone for a server without achievements (old servers)", () => {
    expect(simAttachAchievements(recaps, undefined)).toEqual(recaps);
    expect(simAttachAchievements(recaps, { items: [] })).toEqual(recaps);
  });
  it("adds exactly one story page after the result, only when there is something to show", () => {
    const base = { week: 14, kind: "regular", round: null, your_game: null, scores: [], season_complete: false, champion: null, next_week: 15 } as unknown as SimWeekRecap;
    const facts = { names: {}, lineupWarnings: 0, offers: 0 };
    expect(simRecapPageKeys(base, facts)).not.toContain("achievements");
    const withAch = { ...base, achievements: { new: [ach()], milestones: [] } };
    expect(simRecapPageKeys(withAch, facts).slice(0, 2)).toEqual(["result", "achievements"]);
    expect(simRecapPageTitle("achievements", withAch).title).toBe("Achievement Unlocked");
  });
});

describe("team and player pages", () => {
  it("lists champion trophies newest first", () => {
    const rows = simTeamTrophies([
      { season: 1, year: 2026, season_label: "S1 2026", wins: 10, losses: 4, ties: 0, champion: true },
      { season: 2, year: 2027, season_label: "S2 2027", wins: 7, losses: 6, ties: 1, champion: false },
      { season: 3, year: 2028, season_label: "S3 2028", wins: 12, losses: 2, ties: 0, champion: true },
    ]);
    expect(rows).toEqual([{ label: "S3 2028", record: "12-2" }, { label: "S1 2026", record: "10-4" }]);
    expect(simTeamTrophies(undefined)).toEqual([]);
  });
  it("shows only the badges that name the player", () => {
    const items = [ach({ id: "m", player: { id: "p1", name: "Star", pos: "WR" } }), ach({ id: "n", player: { id: "p2", name: "Other", pos: "RB" } }), ach({ id: "o" })];
    expect(simPlayerBadges(items, "p1").map((a) => a.id)).toEqual(["m"]);
    expect(simPlayerBadges(undefined, "p1")).toEqual([]);
  });
});
