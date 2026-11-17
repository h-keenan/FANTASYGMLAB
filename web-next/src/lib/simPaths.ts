// Endpoint paths for the Fantasy Sim dynasty and reserve routes. Lives apart from simGame.ts (a large module of types and
// view helpers) so api.ts can build request paths at startup without evaluating all of simGame. Byte-identical web/mobile.

/** Endpoint paths for the dynasty and reserve routes (web and mobile call these through their own fetch). */
export function simDynastyPaths(gameId: string) {
  const base = `/v1/sim/games/${encodeURIComponent(gameId)}`;
  return {
    picks: `${base}/picks`,
    rosterMove: `${base}/roster/move`,
    offseason: (pos?: string) => `${base}/offseason${pos ? `?pos=${encodeURIComponent(pos)}` : ""}`,
    rookieDraftStart: `${base}/offseason/rookie-draft/start`,
    rookieDraftPick: `${base}/offseason/rookie-draft/pick`,
    rookieDraftAuto: `${base}/offseason/rookie-draft/auto`,
    startSeason: `${base}/offseason/start-season`,
    dynasty: `${base}/dynasty`,
  };
}
