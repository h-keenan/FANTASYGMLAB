// Twin file: web-next/src/lib/simAchievements.ts and mobile/src/lib/simAchievements.ts stay identical.
//
// Fantasy Sim achievements: presentation of the server's `achievements` payload (modules/sim/game_achievements.py is the one
// source of truth; it derives every badge at view time from the saved game, so old saves get them too). Pure and import-free:
// types, rarity colours, dates, the recap banner model, the home module summary and the team / player badge rows. No React, no storage.

export type SimAchievementRarity = "common" | "rare" | "epic";
export type SimAchievementTone = "good" | "bad" | "neutral";
export type SimAchievementScope = "season" | "career";

export interface SimAchievementProgress {
  current: number;
  target: number;
  /** "11-0, 3 games left", "30 of 50 wins". */
  text: string;
}

export interface SimAchievement {
  id: string;
  key: string;
  scope: SimAchievementScope;
  rarity: SimAchievementRarity;
  tone: SimAchievementTone;
  /** A server icon key (see simAchievementGlyph). */
  icon: string;
  name: string;
  detail: string;
  unlocked: boolean;
  season_no: number | null;
  year: number | null;
  /** The shared season label ("S3 2028"). */
  season_label: string;
  week: number | null;
  /** season_no * 100 + week: newest unlock sorts first. */
  at: number | null;
  progress: SimAchievementProgress | null;
  tier: number | null;
  player: { id: string; name: string; pos: string | null } | null;
}

/** A "WIN #10, still perfect" style banner for the week just played (not a stored badge). */
export interface SimMilestoneBanner {
  kind: "perfect_run" | "win_number" | "winless_watch";
  tone: SimAchievementTone;
  icon: string;
  confetti: boolean;
  headline: string;
  sub: string;
}

export interface SimAchievementCounts {
  unlocked?: number;
  epic?: number;
  rare?: number;
  common?: number;
  locked?: number;
}

export interface SimAchievementsPayload {
  items: SimAchievement[];
  counts?: SimAchievementCounts;
  /** Advance / sim-to responses only: what the weeks just played unlocked, and the milestone banners of the first one. */
  new?: SimAchievement[];
  milestones?: SimMilestoneBanner[];
}

/** What the recap story carries for one played week. */
export interface SimRecapAchievements {
  new: SimAchievement[];
  milestones: SimMilestoneBanner[];
}

const RARITY_RANK: Record<SimAchievementRarity, number> = { epic: 3, rare: 2, common: 1 };
const RARITY_LABEL: Record<SimAchievementRarity, string> = { epic: "Epic", rare: "Rare", common: "Common" };

export const simAchievementRarityLabel = (r: SimAchievementRarity): string => RARITY_LABEL[r] ?? "Common";

/**
 * The semantic colour token of a badge. Gold (premium) belongs to epic wins only; a sympathetic or bad-luck badge is never gold
 * and never green (danger), rare is accent, common good is success, neutral is accent.
 */
export function simAchievementColor(a: Pick<SimAchievement, "rarity" | "tone" | "unlocked">): string {
  if (!a.unlocked) return "var(--color-text-muted)";
  if (a.tone === "bad") return "var(--color-danger)";
  if (a.rarity === "epic" && a.tone === "good") return "var(--color-premium)";
  if (a.rarity === "rare" || a.tone === "neutral") return "var(--color-accent)";
  return "var(--color-success)";
}

/** The SimGlyph a server icon key draws (the app has one glyph set; every key maps to one of its names). */
export function simAchievementGlyph(icon: string): "trophy" | "hot" | "cold" | "spark" | "team" | "matchup" | "alert" | "standings" | "trade" | "waiver" | "check" | "bye" {
  switch (icon) {
    case "trophy":
    case "crown":
      return "trophy";
    case "flame":
      return "hot";
    case "snow":
      return "cold";
    case "bolt":
    case "rocket":
    case "star":
      return "spark";
    case "shield":
      return "team";
    case "target":
      return "matchup";
    case "heart":
      return "alert";
    case "fall":
      return "standings";
    case "swap":
      return "trade";
    case "wand":
      return "waiver";
    case "calendar":
      return "bye";
    default:
      return "check";
  }
}

/** "S3 2028 · Wk 14" (a career badge with no date yet is ""). */
export function simAchievementDate(a: Pick<SimAchievement, "season_label" | "week" | "unlocked">): string {
  if (!a.unlocked) return "";
  const label = a.season_label || "";
  return a.week != null && a.week > 0 ? (label ? `${label} · Wk ${a.week}` : `Wk ${a.week}`) : label;
}

/** The detail line of an opened badge: what it is, how rare, and when (or how far along). */
export function simAchievementLine(a: SimAchievement): string {
  if (!a.unlocked) return a.progress ? `${a.progress.text}.` : a.detail;
  return a.detail;
}

export const simAchievementProgressPct = (p: SimAchievementProgress | null | undefined): number =>
  p && p.target > 0 ? Math.max(0, Math.min(100, Math.round((p.current / p.target) * 100))) : 0;

const byNewest = (a: SimAchievement, b: SimAchievement) => (b.at ?? 0) - (a.at ?? 0) || RARITY_RANK[b.rarity] - RARITY_RANK[a.rarity] || a.id.localeCompare(b.id);

export const simAchievementsUnlocked = (items: readonly SimAchievement[] | null | undefined): SimAchievement[] =>
  (items ?? []).filter((a) => a.unlocked).sort(byNewest);

/** Locked badges closest to done first (a progress ratio, then rarity). */
export const simAchievementsLocked = (items: readonly SimAchievement[] | null | undefined): SimAchievement[] =>
  (items ?? [])
    .filter((a) => !a.unlocked)
    .sort((a, b) => simAchievementProgressPct(b.progress) - simAchievementProgressPct(a.progress) || RARITY_RANK[b.rarity] - RARITY_RANK[a.rarity] || a.id.localeCompare(b.id));

export interface SimAchievementGroup {
  key: "season" | "career" | "locked";
  title: string;
  items: SimAchievement[];
}

/** The module body: this season's badges (newest first), the career ladder, then what is still locked. Empty groups are dropped. */
export function simAchievementGroups(payload: SimAchievementsPayload | null | undefined, seasonNo?: number | null): SimAchievementGroup[] {
  const unlocked = simAchievementsUnlocked(payload?.items);
  const now = seasonNo != null ? unlocked.filter((a) => a.scope === "season" && a.season_no === seasonNo) : [];
  const older = unlocked.filter((a) => a.scope === "season" && !now.includes(a));
  const career = unlocked.filter((a) => a.scope === "career");
  return [
    { key: "season" as const, title: seasonNo != null ? "This season" : "Season badges", items: seasonNo != null ? now : older },
    ...(seasonNo != null ? [{ key: "season" as const, title: "Earlier seasons", items: older }] : []),
    { key: "career" as const, title: "Career", items: career },
    { key: "locked" as const, title: "Still to earn", items: simAchievementsLocked(payload?.items) },
  ].filter((g) => g.items.length > 0);
}

export interface SimAchievementsPart {
  key: string;
  text: string;
  tone?: "success" | "danger" | "warning" | "muted" | "accent" | "action";
  strong?: boolean;
}

/** The collapsed line of the Achievements module: "4 unlocked · 1 epic · next: Perfect Season 11-0, 3 games left". */
export function simAchievementsParts(payload: SimAchievementsPayload | null | undefined): SimAchievementsPart[] {
  const items = payload?.items ?? [];
  const unlocked = items.filter((a) => a.unlocked);
  if (items.length === 0) return [{ key: "n", text: "Play a week to start earning badges", tone: "muted" }];
  const epic = unlocked.filter((a) => a.rarity === "epic").length;
  const next = simAchievementsLocked(items)[0];
  const latest = simAchievementsUnlocked(items)[0];
  const parts: SimAchievementsPart[] = [
    { key: "n", text: `${unlocked.length} unlocked`, tone: unlocked.length ? "accent" : "muted", strong: true },
    epic > 0 ? { key: "epic", text: `${epic} epic`, tone: "warning" } : { key: "epic", text: "" },
    next ? { key: "next", text: `next: ${next.name}${next.progress ? ` (${next.progress.text})` : ""}` } : latest ? { key: "latest", text: `latest: ${latest.name}` } : { key: "x", text: "" },
  ];
  return parts.filter((p) => p.text);
}

// --- the recap banner

export interface SimRecapAchievementModel {
  tone: "premium" | "success" | "danger" | "warning" | "accent";
  /** The big word: "Perfect Season", "WIN #10, still perfect", "Winless... the #1 pick is yours". */
  headline: string;
  sub: string;
  eyebrow: string;
  trophy: boolean;
  /** One-shot confetti: a perfect / undefeated / title-run season only (never under reduced motion, never for a loss). */
  celebrate: boolean;
  /** The badges unlocked this week (hero first). */
  items: SimAchievement[];
  /** Milestone banners that do not repeat a badge. */
  banners: SimMilestoneBanner[];
}

const HERO_ORDER = ["perfect_season", "three_peat", "back_to_back", "champion", "undefeated_regular", "unbeaten_regular", "underdog", "record_season", "worst_to_first", "record_week", "winless", "tank_commander", "heartbreaker"];
const CONFETTI_KEYS = new Set(["perfect_season", "three_peat", "back_to_back", "champion", "undefeated_regular", "underdog"]);

/** Does this week have anything to celebrate (or console)? The recap shows an Achievements page only then. */
export const simRecapHasAchievements = (a: SimRecapAchievements | null | undefined): boolean => Boolean(a && (a.new.length > 0 || a.milestones.length > 0));

function heroRank(a: SimAchievement): number {
  const i = HERO_ORDER.indexOf(a.key);
  return i >= 0 ? i : HERO_ORDER.length + (3 - RARITY_RANK[a.rarity]);
}

/** A sympathetic line for the tank: the #1 pick, or a kind word when it is not yours. */
function winlessHeadline(a: SimAchievement): string {
  return a.detail.includes("#1 pick is yours") ? "Winless... the #1 pick is yours" : "Winless... it happens to the best of us";
}

export function simRecapAchievementModel(a: SimRecapAchievements | null | undefined): SimRecapAchievementModel | null {
  if (!a || !simRecapHasAchievements(a)) return null;
  const items = [...a.new].sort((x, y) => heroRank(x) - heroRank(y) || x.id.localeCompare(y.id));
  const hero = items[0];
  const banner = a.milestones[0];
  const perfectSeason = items.some((i) => i.key === "perfect_season");
  if (hero) {
    const sad = hero.key === "winless";
    const tone: SimRecapAchievementModel["tone"] = sad ? "danger" : hero.tone === "bad" ? "warning" : hero.rarity === "epic" && hero.tone === "good" ? "premium" : hero.rarity === "rare" ? "accent" : "success";
    return {
      tone,
      eyebrow: hero.scope === "career" ? "Career milestone" : "Achievement unlocked",
      headline: sad ? winlessHeadline(hero) : hero.name,
      sub: sad ? hero.detail.replace(" The #1 pick is yours.", "") : hero.detail,
      trophy: !sad && (hero.rarity !== "common" || hero.tone === "good"),
      celebrate: items.some((i) => CONFETTI_KEYS.has(i.key)) || perfectSeason,
      items,
      banners: perfectSeason ? [] : a.milestones,
    };
  }
  return {
    tone: banner.tone === "bad" ? "danger" : "success",
    eyebrow: "Milestone",
    headline: banner.headline,
    sub: banner.sub,
    trophy: false,
    celebrate: banner.confetti,
    items: [],
    banners: a.milestones.slice(1),
  };
}

/**
 * The recaps of one advance with their weeks' achievements attached. Every badge belongs to the week it unlocked in; the milestone
 * banners belong to the first recap (the week the player just played). A server without achievements leaves the recaps as they were.
 */
export function simAttachAchievements<T extends { week: number }>(recaps: readonly T[], payload: SimAchievementsPayload | null | undefined): (T & { achievements?: SimRecapAchievements })[] {
  if (!payload || !Array.isArray(payload.new)) return [...recaps];
  const fresh = payload.new;
  return recaps.map((r, i) => {
    const mine = fresh.filter((a) => a.week === r.week);
    const banners = i === 0 ? (payload.milestones ?? []) : [];
    return mine.length || banners.length ? { ...r, achievements: { new: mine, milestones: banners } } : { ...r };
  });
}

// --- team and player pages

export interface SimTrophyRow {
  label: string;
  /** "12-2" */
  record: string;
}

/** The champion trophies of a team's history, newest first (a team with none returns []). */
export function simTeamTrophies(seasons: readonly { season: number; year: number | null; season_label?: string; wins: number; losses: number; ties: number; champion: boolean }[] | null | undefined): SimTrophyRow[] {
  return [...(seasons ?? [])]
    .filter((s) => s.champion)
    .sort((a, b) => b.season - a.season)
    .map((s) => ({ label: s.season_label || (s.year ? `S${s.season} ${s.year}` : `S${s.season}`), record: s.ties ? `${s.wins}-${s.losses}-${s.ties}` : `${s.wins}-${s.losses}` }));
}

/** Your own team's season badges and career ladder for the team page (opponents' pages show trophies only). */
export const simTeamBadges = (payload: SimAchievementsPayload | null | undefined, limit = 6): SimAchievement[] => simAchievementsUnlocked(payload?.items).slice(0, limit);

/** The badges that name one player (League MVP, Rookie of the Year, the trade or waiver that landed him). */
export const simPlayerBadges = (items: readonly SimAchievement[] | null | undefined, playerId: string): SimAchievement[] =>
  simAchievementsUnlocked(items).filter((a) => a.player?.id === playerId);
