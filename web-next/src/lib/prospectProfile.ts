// Shared (web + mobile twin, byte-identical): the college prospect detail sheet's payload types and presentation rules
// (GET /v1/scouting/prospects/{id}/profile, modules/college_scouting.py build_prospect_profile). Import-free.
//
// Every stat is College Football Data's (cited on screen). Fantasy points are derived from those lines and labelled so.
// Nothing here invents a number: a missing value is "no data", never a zero.

export interface ProspectStatLine {
  passing?: Record<string, number>;
  rushing?: Record<string, number>;
  receiving?: Record<string, number>;
}

export interface ProspectSeason extends ProspectStatLine {
  season: number;
  team: string | null;
  fantasy_points: number | null;
}

export interface ProspectGame extends ProspectStatLine {
  week: number;
  opponent: string | null;
  fantasy_points: number | null;
}

export interface ProspectAdvanced {
  season: number;
  ppa: { avg?: Record<string, number>; total?: Record<string, number> } | null;
  usage: Record<string, number> | null;
}

export interface ProspectRecruiting {
  year: number | null;
  stars: number | null;
  rating: number | null;
  national_rank: number | null;
  high_school: string | null;
  city: string | null;
  state: string | null;
}

export interface ProspectAdp {
  adp: number;
  adp_formatted?: string | null;
  drafts?: number | null;
  label: string;
  source: { source: string; url: string; as_of?: string | null; total_drafts?: number | null } | null;
}

export interface ProspectProfileResponse {
  ok: boolean;
  reason?: string;
  prospect?: {
    id: string;
    name: string;
    position: string;
    school: string;
    draft_year: number | null;
    drafted: boolean;
    nfl_team: string | null;
    draft_round: number | null;
    draft_pick: number | null;
    sleeper_player_id: string | null;
  };
  bio?: { class_year: number | null; height_in: number | null; weight_lb: number | null; hometown: string | null; school_logo_url: string | null };
  stats_available?: boolean;
  seasons?: ProspectSeason[];
  weekly?: { season: number; games: ProspectGame[] } | null;
  fantasy_rules?: string;
  advanced?: ProspectAdvanced | null;
  advanced_available?: boolean;
  /** The server withheld advanced metrics because the caller is not Pro. */
  advanced_locked?: boolean;
  recruiting?: ProspectRecruiting | null;
  adp?: ProspectAdp | null;
  source?: { name: string; url: string; detail?: string | null; as_of?: string | null };
}

export interface ProspectTile {
  label: string;
  value: string;
  note: string;
  percentile: null;
}

const CLASS_LABELS: Record<number, string> = { 1: "Freshman", 2: "Sophomore", 3: "Junior", 4: "Senior" };

/** 76 -> 6'4" */
export function heightLabel(inches: number | null | undefined): string | null {
  if (!inches || inches < 48) return null;
  return `${Math.floor(inches / 12)}'${Math.round(inches % 12)}"`;
}

export function classYearLabel(classYear: number | null | undefined): string | null {
  if (!classYear) return null;
  return CLASS_LABELS[classYear] ?? "Senior";
}

/** The header's second line, e.g. "Class of 2027 · 6'4" · 215 lb". Only what is on file. */
export function prospectMetaLine(draftYear: number | null | undefined, bio: ProspectProfileResponse["bio"] | null | undefined): string {
  const bits = [
    draftYear ? `Class of ${draftYear}` : null,
    heightLabel(bio?.height_in),
    bio?.weight_lb ? `${bio.weight_lb} lb` : null,
  ].filter((bit): bit is string => Boolean(bit));
  return bits.join(" · ");
}

function tile(label: string, value: number | string | null | undefined, note = ""): ProspectTile | null {
  if (value == null || value === "") return null;
  return { label, value: typeof value === "number" ? value.toLocaleString("en-US") : value, note, percentile: null };
}

function fixed(value: number | undefined, digits = 1): string | null {
  return value == null ? null : value.toFixed(digits);
}

function compact(tiles: Array<ProspectTile | null>): ProspectTile[] {
  return tiles.filter((t): t is ProspectTile => t != null);
}

/** Season (or any stat line) as stat tiles, by position. Passing for QB, rushing for RB, receiving for WR/TE; the other lines follow when he has them. */
export function lineTiles(line: ProspectStatLine, position: string): ProspectTile[] {
  const pass = line.passing;
  const rush = line.rushing;
  const rec = line.receiving;
  const passing = pass
    ? compact([
        tile("Pass yds", pass.yds),
        tile("Pass TD", pass.td),
        tile("INT", pass.int),
        pass.pct != null ? tile("Comp %", `${(pass.pct <= 1 ? pass.pct * 100 : pass.pct).toFixed(1)}%`) : pass.cmp != null && pass.att ? tile("Comp %", `${((pass.cmp / pass.att) * 100).toFixed(1)}%`) : null,
        tile("Yds/att", fixed(pass.ypa) ?? (pass.att && pass.yds != null ? (pass.yds / pass.att).toFixed(1) : null)),
      ])
    : [];
  const rushing = rush
    ? compact([tile("Rush yds", rush.yds), tile("Rush TD", rush.td), tile("Carries", rush.car), tile("Yds/carry", fixed(rush.ypc) ?? (rush.car && rush.yds != null ? (rush.yds / rush.car).toFixed(1) : null))])
    : [];
  const receiving = rec
    ? compact([tile("Rec", rec.rec), tile("Rec yds", rec.yds), tile("Rec TD", rec.td), tile("Yds/rec", fixed(rec.ypr) ?? (rec.rec && rec.yds != null ? (rec.yds / rec.rec).toFixed(1) : null))])
    : [];
  const pos = position.toUpperCase();
  const order = pos === "QB" ? [passing, rushing, receiving] : pos === "RB" ? [rushing, receiving, passing] : [receiving, rushing, passing];
  // His main line in full; the other lines just their two headline numbers, so the grid stays a glance.
  return order.flatMap((tiles, index) => (index === 0 ? tiles : tiles.slice(0, 2)));
}

/** "312 pass yds · 3 TD" / "7 rec · 100 yds · 1 TD": one line for a game. */
export function gameStatLine(game: ProspectStatLine, position: string): string {
  const bits: string[] = [];
  const { passing: p, rushing: r, receiving: c } = game;
  const parts: Array<[string, string[]]> = [];
  if (p) parts.push(["pass", [p.yds != null ? `${p.yds} pass yds` : "", p.td ? `${p.td} pass TD` : "", p.int ? `${p.int} INT` : ""]]);
  if (r) parts.push(["rush", [r.car != null ? `${r.car} car` : "", r.yds != null ? `${r.yds} rush yds` : "", r.td ? `${r.td} rush TD` : ""]]);
  if (c) parts.push(["rec", [c.rec != null ? `${c.rec} rec` : "", c.yds != null ? `${c.yds} rec yds` : "", c.td ? `${c.td} rec TD` : ""]]);
  const lead = position.toUpperCase() === "QB" ? "pass" : position.toUpperCase() === "RB" ? "rush" : "rec";
  parts.sort((a, b) => (a[0] === lead ? -1 : b[0] === lead ? 1 : 0));
  for (const [, list] of parts) bits.push(...list.filter(Boolean));
  return bits.join(" · ");
}

export interface ProspectWeeklySeries {
  weeks: { week: number; fantasy_points_ppr: number | null; snap_share: null }[];
  season: number;
}

/** The weekly rows in the one shape the shared weekly chart takes (college fantasy points per game). Null with no games. */
export function prospectWeeklySeries(weekly: ProspectProfileResponse["weekly"]): ProspectWeeklySeries | null {
  const games = weekly?.games ?? [];
  const weeks = games
    .filter((g) => g.fantasy_points != null)
    .map((g) => ({ week: g.week, fantasy_points_ppr: g.fantasy_points, snap_share: null as null }));
  return weeks.length > 0 && weekly ? { weeks, season: weekly.season } : null;
}

function pct(value: number | undefined): string | null {
  return value == null ? null : `${Math.round(value * 100)}%`;
}

function signed(value: number | undefined, digits = 2): string | null {
  if (value == null) return null;
  const text = value.toFixed(digits);
  return value > 0 ? `+${text}` : text;
}

/** Advanced metrics (Pro): predicted points added per play and usage (share of his team's plays). Both are CFBD's; neither is a rating of ours. */
export function advancedTiles(advanced: ProspectAdvanced | null | undefined, position: string): ProspectTile[] {
  if (!advanced) return [];
  const avg = advanced.ppa?.avg ?? {};
  const total = advanced.ppa?.total ?? {};
  const usage = advanced.usage ?? {};
  const pos = position.toUpperCase();
  const lead = pos === "QB" ? "pass" : pos === "RB" ? "rush" : "pass";
  return compact([
    tile("PPA / play", signed(avg.all), "points added per play"),
    avg[lead] != null ? tile(lead === "pass" ? "PPA passing" : "PPA rushing", signed(avg[lead]), "per play") : null,
    total.all != null ? tile("Total PPA", signed(total.all, 1), "season") : null,
    tile("Usage", pct(usage.overall), "of team plays"),
    usage.pass != null && pos !== "RB" ? tile("Pass usage", pct(usage.pass), "of team pass plays") : null,
    usage.rush != null && pos === "RB" ? tile("Rush usage", pct(usage.rush), "of team rush plays") : null,
  ]);
}

/** Recruiting profile tiles (CFBD recruiting feed): stars, national rank, rating, class. */
export function recruitingTiles(rec: ProspectRecruiting | null | undefined): ProspectTile[] {
  if (!rec) return [];
  return compact([
    rec.stars ? tile("Stars", `${rec.stars}-star`, "high school recruit") : null,
    tile("National rank", rec.national_rank ? `#${rec.national_rank}` : null, "in his class"),
    tile("Rating", rec.rating != null ? rec.rating.toFixed(4) : null, "recruiting rating"),
    tile("Signed", rec.year ? String(rec.year) : null, "recruiting class"),
  ]);
}

export function hometownLine(rec: ProspectRecruiting | null | undefined, bioHometown: string | null | undefined): string | null {
  const place = [rec?.city, rec?.state].filter(Boolean).join(", ") || bioHometown || null;
  const school = rec?.high_school || null;
  if (place && school) return `${place} · ${school}`;
  return place || school;
}

/** The hero's Rookie ADP tile. Off-season there is none: "No ADP yet", never a stale or guessed number. */
export function adpHeroTile(adp: ProspectAdp | null | undefined): { label: string; value: string; note: string } {
  if (!adp) return { label: "Rookie ADP", value: "—", note: "No ADP yet" };
  return { label: "Rookie ADP", value: adp.adp_formatted || adp.adp.toFixed(1), note: adp.label };
}

/** The hero's round tile, from the crowd's average round projection. */
export function roundHeroTile(avgRound: number | null | undefined, scoutCount: number): { label: string; value: string; note: string } {
  if (avgRound == null || scoutCount <= 0) return { label: "Proj. round", value: "—", note: "No projection yet" };
  return { label: "Proj. round", value: String(Math.max(1, Math.round(avgRound))), note: "crowd average" };
}

/** The post-draft hand-off: a drafted, mapped prospect opens the normal NFL player card by his Sleeper id. */
export function handOffPlayerId(prospect: { sleeper_player_id?: string | null } | null | undefined): string | null {
  const id = prospect?.sleeper_player_id;
  return id ? String(id) : null;
}

export const PROSPECT_SOURCE_NAME = "College Football Data";
export const PROSPECT_SOURCE_URL = "https://collegefootballdata.com";

export const PROSPECT_NO_STATS = "They fill in weekly during the season.";

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function asRows<T>(value: unknown): T[] {
  return Array.isArray(value) ? (value.filter((v) => v && typeof v === "object") as T[]) : [];
}

/** The payload with every list defaulted, so a missing field renders an empty state instead of crashing the sheet. */
export function normalizeProspectProfile(raw: unknown): ProspectProfileResponse {
  const r = asRecord(raw);
  const weekly = r.weekly && typeof r.weekly === "object" ? asRecord(r.weekly) : null;
  return {
    ...r,
    ok: r.ok === true,
    seasons: asRows<ProspectSeason>(r.seasons),
    weekly: weekly ? ({ ...weekly, games: asRows<ProspectGame>(weekly.games) } as ProspectProfileResponse["weekly"]) : null,
    advanced: r.advanced && typeof r.advanced === "object" ? (r.advanced as ProspectAdvanced) : null,
    recruiting: r.recruiting && typeof r.recruiting === "object" ? (r.recruiting as ProspectRecruiting) : null,
    adp: r.adp && typeof r.adp === "object" ? (r.adp as ProspectAdp) : null,
  } as ProspectProfileResponse;
}
