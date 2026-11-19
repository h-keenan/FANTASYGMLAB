/**
 * Fantasy Sim load-failure copy, one definition for web and app (byte-identical lib twin) so the two clients cannot drift
 * again. Wording: "Could not load <the thing>", with the shared hint below as the body. No terminal period on titles.
 */

export const SIM_LOAD_ERROR = {
  home: "Could not load your home screen",
  players: "Could not load players",
  outlook: "Could not load the outlook",
  draft: "Could not load the draft",
  league: "Could not load the league",
  rosters: "Could not load the rosters",
  offseason: "Could not load the offseason",
  block: "Could not load your block",
  inbox: "Could not load your inbox",
  teams: "Could not load the teams",
  team: "Could not load this team",
  teamHistory: "Could not load this team's history",
  lineup: "Could not load your lineup",
  finalResult: "Could not load your final result",
  playerHistory: "Could not load this player's history",
  pastSeasons: "Could not load past seasons",
  roster: "Could not load rosters",
  simSeasons: "Could not load this player's sim seasons",
  options: "Could not load the options",
} as const;

export const SIM_LOAD_ERROR_HINT = "Check your connection and try again.";
