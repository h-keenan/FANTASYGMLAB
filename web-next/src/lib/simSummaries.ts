/**
 * The collapsed summary lines of the Fantasy Sim home modules (CompactModule `parts`). A collapsed module reads like
 * a status line, never an empty header: "2 offers · Taco Tuesday expires wk 4". Pure and import-light;
 * byte-identical twin of mobile/src/lib/simSummaries.ts.
 */
import { compactCount, type CompactPart } from "./compactModule";
import { playerSurname } from "./playerNameDisplay";

const last = (name: string): string => playerSurname(name) || name;

export function simInboxParts(inbox: { count: number; items: { from: { name: string }; expires_week: number }[] } | null | undefined): CompactPart[] {
  const count = inbox?.count ?? 0;
  if (!inbox || count === 0) return [{ key: "n", text: "No offers waiting", tone: "muted" }];
  const first = inbox.items[0];
  return [
    { key: "n", text: compactCount(count, "offer"), tone: "accent", strong: true },
    ...(first ? [{ key: "from", text: `from ${first.from.name}` }, { key: "exp", text: `expires wk ${first.expires_week}`, tone: "muted" as const }] : []),
  ];
}

export function simWaiverParts(list: { player: { name: string }; gain_now: number; gain_ros: number }[]): CompactPart[] {
  if (list.length === 0) return [{ key: "n", text: "Nothing beats your roster", tone: "muted" }];
  const top = list[0];
  const gain = Math.max(top.gain_now, top.gain_ros);
  return [
    { key: "n", text: compactCount(list.length, "target"), tone: "success", strong: true },
    { key: "top", text: `top: ${last(top.player.name)}` },
    ...(gain > 0 ? [{ key: "gain", text: `+${gain.toFixed(1)} pts`, tone: "success" as const }] : []),
  ];
}

export function simInjuryParts(list: { starting?: boolean; player: { name: string } }[]): CompactPart[] {
  if (list.length === 0) return [{ key: "n", text: "Everyone is healthy", tone: "success" }];
  const starters = list.filter((i) => i.starting);
  return [
    { key: "n", text: `${list.length} out`, tone: "danger", strong: true },
    ...(starters.length ? [{ key: "st", text: `${starters.length} starting`, tone: "warning" as const }] : []),
    { key: "who", text: list.slice(0, 2).map((i) => last(i.player.name)).join(", ") },
  ];
}

export function simByeParts(alerts: { covered: boolean; week: number }[]): CompactPart[] {
  const open = alerts.filter((a) => !a.covered);
  if (open.length === 0) return [{ key: "n", text: "Every bye is covered", tone: "success" }];
  return [
    { key: "n", text: `${open.length} need cover`, tone: "warning", strong: true },
    { key: "wk", text: `next bye wk ${Math.min(...open.map((a) => a.week))}` },
  ];
}

export function simStandingsParts(standings: { in_playoffs?: boolean; playoff_spots?: number; rows: { is_you?: boolean; rank: number; wins: number; losses: number; ties?: number }[] } | null | undefined): CompactPart[] {
  const mine = standings?.rows.find((r) => r.is_you);
  if (!standings || !mine) return [{ key: "n", text: "Standings after Week 1", tone: "muted" }];
  return [
    { key: "rank", text: `#${mine.rank}`, strong: true },
    { key: "rec", text: `${mine.wins}-${mine.losses}${mine.ties ? `-${mine.ties}` : ""}` },
    { key: "po", text: standings.in_playoffs ? "In the playoffs" : "Outside the cut", tone: standings.in_playoffs ? "success" : "warning" },
  ];
}

export function simLeagueParts(standings: Parameters<typeof simStandingsParts>[0], moves: number, hotCold?: { hot: number; cold: number }): CompactPart[] {
  const mine = standings?.rows.find((r) => r.is_you);
  return [
    ...(mine ? [{ key: "rank", text: `#${mine.rank}`, strong: true }, { key: "po", text: standings!.in_playoffs ? "In" : "Out", tone: (standings!.in_playoffs ? "success" : "warning") as "success" | "warning" }] : []),
    ...(hotCold && hotCold.hot + hotCold.cold > 0 ? [{ key: "hc", text: `${hotCold.hot} hot · ${hotCold.cold} cold` }] : []),
    ...(moves > 0 ? [{ key: "mv", text: compactCount(moves, "move") }] : []),
  ];
}

// ---------------------------------------------------------------------------
// Team tab and standings (2026-11-14 UI pass)

interface SummaryPlayer { status?: string | null; pos?: string }

/** "8 starters · proj 121.4 · 1 issue": the collapsed Lineup module. */
export function simLineupParts(lineup: { slots: { slot: string; player: SummaryPlayer | null }[]; projected_total?: number; warnings?: unknown[] }): CompactPart[] {
  const filled = lineup.slots.filter((s) => s.player).length;
  const out = lineup.slots.filter((s) => s.player?.status === "out").length;
  const bye = lineup.slots.filter((s) => s.player?.status === "bye").length;
  const empty = lineup.slots.length - filled;
  const issues = (lineup.warnings ?? []).length;
  return [
    { key: "n", text: `${lineup.slots.length} starters`, strong: true },
    lineup.projected_total != null ? { key: "proj", text: `proj ${lineup.projected_total.toFixed(1)}`, tone: "accent" as const } : null,
    issues > 0 ? { key: "issues", text: compactCount(issues, "issue"), tone: "warning" as const } : { key: "ok", text: "set", tone: "success" as const },
    out > 0 ? { key: "out", text: `${out} out`, tone: "danger" as const } : null,
    bye > 0 ? { key: "bye", text: `${bye} on bye`, tone: "warning" as const } : null,
    empty > 0 ? { key: "empty", text: `${empty} empty`, tone: "danger" as const } : null,
  ].filter(Boolean) as CompactPart[];
}

/** "8 bench · 16/16 spots · QB2 RB3 · 1 out": the collapsed Bench module. */
export function simBenchParts(bench: SummaryPlayer[], rosterSize?: number, rosterLimit?: number): CompactPart[] {
  if (bench.length === 0) return [{ key: "n", text: "Empty bench", tone: "muted" }];
  const byPos = new Map<string, number>();
  for (const p of bench) if (p.pos) byPos.set(p.pos, (byPos.get(p.pos) ?? 0) + 1);
  const mix = [...byPos.entries()].sort((a, b) => b[1] - a[1]).slice(0, 4).map(([pos, n]) => `${pos}${n}`).join(" ");
  const out = bench.filter((p) => p.status === "out").length;
  const bye = bench.filter((p) => p.status === "bye").length;
  const over = rosterSize != null && rosterLimit != null && rosterSize > rosterLimit;
  return [
    { key: "n", text: `${bench.length} bench`, strong: true },
    rosterSize != null && rosterLimit != null ? { key: "spots", text: `${rosterSize}/${rosterLimit} spots`, tone: over ? ("danger" as const) : ("muted" as const) } : null,
    mix ? { key: "mix", text: mix } : null,
    out > 0 ? { key: "out", text: `${out} out`, tone: "danger" as const } : null,
    bye > 0 ? { key: "bye", text: `${bye} on bye`, tone: "warning" as const } : null,
  ].filter(Boolean) as CompactPart[];
}

export interface SimStandingHeroModel {
  value: string;
  context: string;
  tone: "success" | "warning" | "danger" | "accent";
}

/** The Standings hero: "#3" and "1-2 · 4th in points · 1 game back of the 6th seed". Null when you are not in the table. */
export function simStandingHero(rows: { rank?: number; wins: number; losses: number; ties: number; pf: number; is_you: boolean }[], playoffTeams: number): SimStandingHeroModel | null {
  const idx = rows.findIndex((r) => r.is_you);
  if (idx < 0) return null;
  const you = rows[idx];
  const rank = you.rank ?? idx + 1;
  const record = `${you.wins}-${you.losses}${you.ties ? `-${you.ties}` : ""}`;
  const pfRank = 1 + rows.filter((r) => r.pf > you.pf).length;
  const ord = (n: number) => { const v = n % 100; return v >= 11 && v <= 13 ? `${n}th` : `${n}${({ 1: "st", 2: "nd", 3: "rd" } as Record<number, string>)[n % 10] ?? "th"}`; };
  const gp = (r: { wins: number; losses: number }) => r.wins - r.losses;
  let status = "";
  let tone: SimStandingHeroModel["tone"] = "accent";
  if (playoffTeams > 0 && rows.length > playoffTeams) {
    const cut = rows[playoffTeams - 1];
    const firstOut = rows[playoffTeams];
    if (idx < playoffTeams) {
      const lead = (gp(you) - gp(firstOut)) / 2;
      status = lead > 0 ? `${lead % 1 === 0 ? lead : lead.toFixed(1)} ${lead === 1 ? "game" : "games"} clear of the cut` : "on the cut line";
      tone = lead > 0 ? "success" : "warning";
    } else {
      const back = (gp(cut) - gp(you)) / 2;
      status = `${back % 1 === 0 ? back : back.toFixed(1)} ${back === 1 ? "game" : "games"} back of the ${ord(playoffTeams)} seed`;
      tone = back <= 1 ? "warning" : "danger";
    }
  }
  return { value: `#${rank}`, context: [record, `${ord(pfRank)} in points`, status].filter(Boolean).join(" · "), tone };
}

// ---------------------------------------------------------------------------
// Game menu (the "More" sheet): a hero for the season and informative collapsed modules.

/** "Week 4 of 14" + "2-1 · #4 of 12 · PPR · Normal". */
export function simMenuHero(game: {
  status: string;
  week: number;
  you?: { wins: number; losses: number; ties: number; rank: number | null } | null;
  settings: { teams?: number; regular_weeks?: number; scoring?: string };
}, difficultyLabel: string, scoringLabel: string): { label: string; value: string; context: string } {
  const total = game.settings.regular_weeks;
  const value = game.status === "drafting" ? "Draft" : game.status === "complete" ? "Final" : game.status === "playoffs" ? "Playoffs" : total ? `Week ${game.week} of ${total}` : `Week ${game.week}`;
  const y = game.you;
  const record = y ? `${y.wins}-${y.losses}${y.ties ? `-${y.ties}` : ""}` : "";
  const rank = y?.rank != null ? `#${y.rank}${game.settings.teams ? ` of ${game.settings.teams}` : ""}` : "";
  return { label: "Your season", value, context: [record, rank, scoringLabel, difficultyLabel].filter(Boolean).join(" · ") };
}

/** "14 wks · 6 make playoffs · deadline wk 10 · roster 16": the collapsed League rules module. */
export function simRulesParts(s: { regular_weeks?: number; playoff_teams?: number; trade_deadline_week?: number; roster_limit?: number; teams?: number }): CompactPart[] {
  return [
    s.regular_weeks ? { key: "wks", text: `${s.regular_weeks} weeks`, strong: true } : null,
    s.playoff_teams ? { key: "po", text: `${s.playoff_teams} make playoffs` } : null,
    s.trade_deadline_week ? { key: "dl", text: `deadline wk ${s.trade_deadline_week}`, tone: "warning" as const } : null,
    s.roster_limit ? { key: "ros", text: `roster ${s.roster_limit}`, tone: "muted" as const } : null,
  ].filter(Boolean) as CompactPart[];
}
