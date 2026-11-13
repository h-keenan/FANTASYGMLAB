// Shared (web + mobile twin): what the Player Quick View may show from the real world, by where it was opened.
// Inside Fantasy Sim the game's own world is the only source: no real news, real injury / availability notes, real
// depth-chart note, real bye or real contract (coridian_, 2026-11-13: "inside of Fantasy Sim there should not be real
// news in there whatsoever"). The real PQV outside the sim is unchanged. Import-free.

export interface PqvRealWorld {
  fetchNews: boolean;
  showNews: boolean;
  showAvailability: boolean;
  showDepthChartNote: boolean;
  showBye: boolean;
  showContract: boolean;
}

export function pqvRealWorld(isSim: boolean): PqvRealWorld {
  const on = !isSim;
  return { fetchNews: on, showNews: on, showAvailability: on, showDepthChartNote: on, showBye: on, showContract: on };
}

/** The bio the sim may show: the real bye week and contract are dropped inside the sim. */
export function pqvBioForContext<T extends { bye_week: string; contract_status: string }>(bio: T, isSim: boolean): T {
  return isSim ? { ...bio, bye_week: "", contract_status: "" } : bio;
}
