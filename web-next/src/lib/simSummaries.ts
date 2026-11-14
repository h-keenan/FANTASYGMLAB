/**
 * The collapsed summary lines of the Fantasy Sim home modules (CompactModule `parts`). A collapsed module reads like
 * a status line, never an empty header: "2 offers · Taco Tuesday expires wk 4". Pure and import-light;
 * byte-identical twin of mobile/src/lib/simSummaries.ts.
 */
import { compactCount, type CompactPart } from "./compactModule";

const last = (name: string): string => name.trim().split(/\s+/).slice(-1)[0] ?? name;

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
