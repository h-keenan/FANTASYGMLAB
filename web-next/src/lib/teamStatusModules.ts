/**
 * The Today hero as templates (docs/ui-patterns.md "Module templates"): the pure model that turns the four "Your team
 * right now" reads (lib/teamStatus.ts) into one Hero plus the collapsed summaries of three CompactModules (Lineup,
 * Standing, Position rooms). Import-light, byte-identical twin of mobile/src/lib/teamStatusModules.ts.
 */
import type { CompactPart, CompactTone } from "./compactModule";
import type { TeamStatusLineup, TeamStatusMatchup, TeamStatusPosition, TeamStatusStanding } from "./teamStatus";

export interface TeamStatusHeroModel {
  label: string;
  value: string;
  context: string | null;
  tone: "success" | "danger" | "accent";
}

/**
 * One big number: this week's win chance when the matchup is modeled, else the live/final score, else the season
 * standing, else the record. Returns null when none of those exist (the hero is then not drawn at all).
 */
export function teamStatusHeroModel(
  matchup: TeamStatusMatchup | null,
  standing: TeamStatusStanding | null,
): TeamStatusHeroModel | null {
  if (matchup) {
    const week = matchup.week != null ? `Week ${matchup.week}` : "This week";
    const state = matchup.stateLabel ? ` · ${matchup.stateLabel}` : "";
    const proj =
      matchup.myProjected != null && matchup.opponentProjected != null ? ` · Proj ${matchup.myProjected.toFixed(1)} - ${matchup.opponentProjected.toFixed(1)}` : "";
    if (matchup.winPercent != null) {
      return {
        label: "Your win chance",
        value: `${matchup.winPercent}%`,
        context: `${week} vs ${matchup.opponentName}${state}${proj}`,
        tone: matchup.winPercent >= 55 ? "success" : matchup.winPercent <= 45 ? "danger" : "accent",
      };
    }
    if (matchup.live) {
      return {
        label: "Score so far",
        value: `${matchup.live.mine.toFixed(1)} - ${matchup.live.opponent.toFixed(1)}`,
        context: `${week} vs ${matchup.opponentName}${state}`,
        tone: matchup.live.mine >= matchup.live.opponent ? "success" : "danger",
      };
    }
  }
  if (standing && (standing.place || standing.record)) {
    return {
      label: standing.place ? "Standing" : "Record",
      value: standing.place ?? (standing.record as string),
      context: [standing.place ? standing.record : null, standing.playoffOdds ? `Playoff odds ${standing.playoffOdds}` : null, standing.playoffStatus].filter(Boolean).join(" · ") || null,
      tone: standing.tone === "positive" ? "success" : standing.tone === "risk" ? "danger" : "accent",
    };
  }
  return null;
}

/** Collapsed summary of the Lineup module: "1 starter can't play (bye or out) · Best swap: ...". */
export function lineupModuleParts(lineup: TeamStatusLineup): CompactPart[] {
  const tone: CompactTone | undefined = lineup.tone === "risk" ? "danger" : lineup.tone === "positive" ? "success" : undefined;
  const out: CompactPart[] = [{ key: "headline", text: lineup.headline, strong: true, tone }];
  if (lineup.detail) out.push({ key: "detail", text: lineup.detail });
  return out;
}

/** Collapsed summary of the Standing module: "3rd of 12 · 3-5 · Playoff odds 41% · Proj 7-7". */
export function standingModuleParts(standing: TeamStatusStanding): CompactPart[] {
  const tone: CompactTone | undefined = standing.tone === "positive" ? "success" : standing.tone === "risk" ? "danger" : undefined;
  const out: CompactPart[] = [];
  if (standing.place) out.push({ key: "place", text: standing.place, strong: true });
  if (standing.record) out.push({ key: "record", text: standing.record });
  if (standing.playoffOdds) out.push({ key: "odds", text: `Playoff odds ${standing.playoffOdds}`, tone });
  if (standing.projectedRecord) out.push({ key: "proj", text: `Proj ${standing.projectedRecord}` });
  return out;
}

/** Collapsed summary of the Position rooms module: "RB Needs help · QB Strength · WR Solid · TE Solid". */
export function roomsModuleParts(rows: readonly TeamStatusPosition[]): CompactPart[] {
  const sorted = [...rows].sort((a, b) => Number(b.weakest) - Number(a.weakest));
  return sorted.map((row) => ({
    key: row.position,
    text: `${row.position} ${row.label}`,
    strong: row.weakest,
    tone: row.tone === "risk" ? ("danger" as const) : row.tone === "positive" ? ("success" as const) : row.tone === "warning" ? ("warning" as const) : undefined,
  }));
}
