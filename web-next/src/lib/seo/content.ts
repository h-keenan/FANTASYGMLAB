import type { PublicBoard, PublicPlayer } from "./publicValues";
import { playersAt, PLAYER_PAGE_LIMIT } from "./publicValues";
import { POSITION_NAMES, parsePosition } from "./site";

/** A rankings page needs at least this many players to be worth indexing. */
export const MIN_RANKINGS_PLAYERS = 10;
/** Rows shown on a positional rankings page. */
export const RANKINGS_ROWS = 50;
/** Rows shown on the trade value chart. */
export const CHART_ROWS = 100;
/** Minimum distinct data-backed facts a player page needs to be indexable. */
export const MIN_PLAYER_FACTS = 4;

const KNOWN_TRENDS: Record<string, string> = {
  Rising: "rising",
  Stable: "stable",
  Cooling: "cooling",
  Fragile: "fragile",
  Blocked: "blocked",
};

export function trendLabel(trend: string | null): string | null {
  return trend && KNOWN_TRENDS[trend] ? KNOWN_TRENDS[trend] : null;
}

export function isPageEligible(player: PublicPlayer): boolean {
  return player.overall_rank <= PLAYER_PAGE_LIMIT;
}

function positionName(player: PublicPlayer, plural = false): string {
  const key = parsePosition(player.position);
  if (!key) return player.position;
  return plural ? POSITION_NAMES[key].plural : POSITION_NAMES[key].singular;
}

/** Facts for the player page, each backed by a field we actually have. */
export function playerFacts(player: PublicPlayer, board: PublicBoard, superflex: PublicPlayer | null): string[] {
  const facts: string[] = [];
  const posName = positionName(player);
  const article = /^[aeiou]/i.test(posName) ? "an" : "a";
  const where = player.team ? ` for the ${player.team}` : "";
  facts.push(
    player.age !== null
      ? `${player.name} is a ${player.age}-year-old ${posName}${where}.`
      : `${player.name} is ${article} ${posName}${where}.`,
  );
  facts.push(
    `FantasyDesk gives ${player.name} a dynasty value of ${player.score.toLocaleString("en-US")}, which ranks #${player.position_rank} among ${positionName(player, true)} and #${player.overall_rank} overall in a ${board.teams}-team ${board.scoring} 1QB dynasty league.`,
  );
  if (superflex) {
    facts.push(
      `In Superflex his value is ${superflex.score.toLocaleString("en-US")} (#${superflex.position_rank} at the position, #${superflex.overall_rank} overall).`,
    );
  }
  if (player.tier) facts.push(`Our model places him in the ${player.tier} tier.`);
  if (player.years_exp !== null && player.years_exp > 0) {
    facts.push(`He has ${player.years_exp} ${player.years_exp === 1 ? "year" : "years"} of NFL experience.`);
  }
  const trend = trendLabel(player.trend);
  if (trend) facts.push(`FantasyDesk's workload trend signal for him currently reads ${trend}.`);
  if (player.injury_status) facts.push(`Sleeper lists his injury status as ${player.injury_status}.`);
  else if (player.status && player.status !== "Active") facts.push(`His roster status is listed as ${player.status}.`);

  if (player.age !== null) {
    const top = playersAt(board, player.position).slice(0, 24);
    const aged = top.filter((p) => p.age !== null);
    if (aged.length >= 12 && player.position_rank <= 24) {
      const older = aged.filter((p) => (p.age as number) > (player.age as number)).length;
      facts.push(`He is younger than ${older} of the top ${aged.length} ${positionName(player, true)} by dynasty value.`);
    }
  }
  return facts;
}

export function neighbors(player: PublicPlayer, board: PublicBoard): { above: PublicPlayer | null; below: PublicPlayer | null } {
  const peers = playersAt(board, player.position);
  const index = peers.findIndex((p) => p.player_id === player.player_id);
  return { above: index > 0 ? peers[index - 1] : null, below: index >= 0 && index < peers.length - 1 ? peers[index + 1] : null };
}

/** Thin-content gate: enough real facts, and the core fields present. */
export function isPlayerPageIndexable(player: PublicPlayer, board: PublicBoard, superflex: PublicPlayer | null): boolean {
  if (!isPageEligible(player)) return false;
  if (!player.name || !player.position || !parsePosition(player.position)) return false;
  if (!(player.score > 0)) return false;
  return playerFacts(player, board, superflex).length >= MIN_PLAYER_FACTS;
}

export function isRankingsIndexable(players: readonly PublicPlayer[]): boolean {
  return players.length >= MIN_RANKINGS_PLAYERS;
}

export function playerDescription(player: PublicPlayer): string {
  const key = parsePosition(player.position);
  const pos = key ? POSITION_NAMES[key].upper : player.position;
  const team = player.team ? ` (${player.team})` : "";
  return `${player.name}${team} dynasty value: ${pos}${player.position_rank}, #${player.overall_rank} overall, value ${player.score.toLocaleString("en-US")}. Age, tier and workload trend from FantasyDesk.`;
}
