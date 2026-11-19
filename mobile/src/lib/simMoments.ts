// Fantasy Sim "moments": the small celebrations around a draft pick, a played week and a streak, and the Celebrations setting that
// turns them off. Pure and import-free: web and the app keep byte-identical copies (scripts/check_lib_twins.mjs).

/** Per-device storage key of the Celebrations setting. Absent means on: the setting defaults to on. */
export const SIM_CELEBRATIONS_KEY = "fd.sim.celebrations";

export function simCelebrationsParse(raw: string | null | undefined): boolean {
  return raw !== "off";
}

export function simCelebrationsSerialize(on: boolean): string {
  return on ? "on" : "off";
}

/** "Jalen Pruitt" -> "J. Pruitt". Suffixes stay with the surname. */
export function simMomentShortName(name: string | null | undefined): string {
  const parts = String(name ?? "").trim().split(/\s+/).filter(Boolean);
  if (parts.length < 2) return parts[0] ?? "";
  const suffix = /^(jr\.?|sr\.?|ii|iii|iv|v)$/i;
  const last = suffix.test(parts[parts.length - 1]) && parts.length > 2 ? `${parts[parts.length - 2]} ${parts[parts.length - 1]}` : parts[parts.length - 1];
  return `${parts[0][0].toUpperCase()}. ${last}`;
}

export type SimMomentTone = "good" | "neutral" | "warm";

/** The grade a draft pick gets when it lands, from how far the pick went over (or under) his average draft slot. Never an F. */
export function simPickMomentGrade(valueOverAdp: number | null | undefined): { letter: string; tone: SimMomentTone; line: string } {
  const v = typeof valueOverAdp === "number" && Number.isFinite(valueOverAdp) ? valueOverAdp : 0;
  const rounded = Math.round(v);
  const letter = v >= 14 ? "A" : v >= 5 ? "A-" : v >= 1 ? "B+" : v >= -3 ? "B" : v >= -8 ? "C+" : v >= -14 ? "C" : "C-";
  const tone: SimMomentTone = letter.startsWith("A") || letter.startsWith("B") ? "good" : "warm";
  const line = rounded > 0 ? `+${rounded} over his slot` : rounded < 0 ? `${Math.abs(rounded)} under his slot` : "Right on his slot";
  return { letter, tone, line };
}

/** The word under a board row's grade: "+6 slots", "Fair", "-4 slots". */
export function simPickBoardNote(valueOverAdp: number | null | undefined): string {
  const v = Math.round(typeof valueOverAdp === "number" && Number.isFinite(valueOverAdp) ? valueOverAdp : 0);
  if (v === 0 || Math.abs(v) <= 1) return "Fair";
  return `${v > 0 ? "+" : "-"}${Math.abs(v)} slots`;
}

interface StandingRowLike {
  is_you?: boolean;
  wins?: number;
  losses?: number;
  ties?: number;
  rank?: number;
  rank_prev?: number | null;
}

interface StarterRowLike {
  pts?: number;
  flag?: string | null;
  player?: { name?: string } | null;
}

interface RecapLike {
  kind?: string;
  your_game?: {
    result?: string;
    your_pts?: number;
    opp_pts?: number;
    opponent_name?: string;
    optimal_pts?: number;
    starters?: StarterRowLike[];
  } | null;
  standings?: StandingRowLike[] | null;
}

function ordinal(n: number): string {
  const v = n % 100;
  const suffix = v >= 11 && v <= 13 ? "th" : ({ 1: "st", 2: "nd", 3: "rd" } as Record<number, string>)[n % 10] ?? "th";
  return `${n}${suffix}`;
}

export interface SimWeekStamp {
  /** The stamp letter: W, L or T. */
  letter: "W" | "L" | "T";
  tone: SimMomentTone;
  /** "4-2, up to 3rd" / "3-3, still 5th". */
  caption: string;
  /** "Pruitt led you with 31.4" / "Close one, 17.2 points sat on your bench". */
  note: string | null;
  yours: number;
  theirs: number;
  opponent: string;
}

/** What the win / loss stamp says after a played week. Null for a bye or a week with no game. */
export function simWeekStamp(recap: RecapLike | null | undefined): SimWeekStamp | null {
  const g = recap?.your_game;
  if (!g || typeof g.your_pts !== "number" || typeof g.opp_pts !== "number") return null;
  const letter = g.result === "win" ? "W" : g.result === "loss" ? "L" : "T";
  const you = recap?.standings?.find((row) => row.is_you);
  let caption = letter === "W" ? "Win" : letter === "L" ? "Loss" : "Tie";
  if (you && typeof you.wins === "number" && typeof you.losses === "number" && recap?.kind !== "playoff") {
    const record = `${you.wins}-${you.losses}${you.ties ? `-${you.ties}` : ""}`;
    const rank = typeof you.rank === "number" ? you.rank : null;
    const prev = typeof you.rank_prev === "number" ? you.rank_prev : null;
    const move = rank === null ? "" : prev === null || prev === rank ? `, still ${ordinal(rank)}` : rank < prev ? `, up to ${ordinal(rank)}` : `, down to ${ordinal(rank)}`;
    caption = `${record}${move}`;
  }
  const margin = g.your_pts - g.opp_pts;
  const benchLeft = typeof g.optimal_pts === "number" ? Math.round((g.optimal_pts - g.your_pts) * 10) / 10 : 0;
  const top = (g.starters ?? []).filter((s) => s.player?.name && !s.flag && typeof s.pts === "number").sort((a, b) => (b.pts ?? 0) - (a.pts ?? 0))[0];
  let note: string | null = null;
  if (letter === "L" && benchLeft > 0 && benchLeft > Math.abs(margin)) note = `Close one, ${benchLeft.toFixed(1)} points sat on your bench`;
  else if (top && top.player?.name) note = `${simMomentShortName(top.player.name)} led you with ${(top.pts ?? 0).toFixed(1)}`;
  return { letter, tone: letter === "W" ? "good" : "neutral", caption, note, yours: g.your_pts, theirs: g.opp_pts, opponent: g.opponent_name ?? "" };
}

interface AchievementLike {
  key?: string;
  icon?: string;
  detail?: string;
  tier?: number | null;
  progress?: { target?: number } | null;
}

/** The number a streak badge shows in its disc ("5" for a 5-win streak); null for every other badge. */
export function simStreakNumber(a: AchievementLike | null | undefined): number | null {
  if (!a || !/(^|_)streak$/.test(String(a.key ?? "")) ) return null;
  const fromDetail = /(\d+)/.exec(String(a.detail ?? ""));
  if (fromDetail) return Number(fromDetail[1]);
  if (typeof a.tier === "number" && a.tier > 0) return a.tier;
  if (a.progress && typeof a.progress.target === "number") return a.progress.target;
  return null;
}
