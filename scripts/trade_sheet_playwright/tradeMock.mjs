// Mocked main-app API (localhost:8000) for the Trade Analyzer: a 12-team league, 16 players + 6 picks per team.
const NAMES = ["Jaxon Moore","Devin Carter","Malik Ross","Tyrese Boone","Caleb Hunt","Elijah Stone","Noah Banks","Austin Pike","Marcus Lane","Dominic Reyes","Trevor Quinn","Isaiah Webb","Julian Cross","Brandon Holt","Cooper Vance","Rashad Ellis","Landon Frost","Micah Shaw","Xavier Doyle","Terrell Nash","Colton Rhodes","Derrick Moss","Gavin Price","Jerome Tate","Wesley Burke","Anthony Cole","Darius Webb","Kendrick Hale","Preston Lowe","Ronnie Fox","Silas Grant","Theo Barrett","Victor Dunn","Zane Mercer","Andre Keller","Bryce Larkin","Corey Wells","Damon Pryor","Elias Voss","Felix Ward"];
const NFL = ["KC","SF","BUF","PHI","DAL","MIA","CIN","DET","BAL","LAR","GB","MIN"];
const POS = ["QB","RB","WR","RB","WR","TE","WR","RB","QB","WR","TE","RB","WR","WR","RB","TE"];
const TEAM_NAMES = ["Gridiron Goats","Blitz Brigade","Dynasty Dogs","Fourth & Long","Hail Marys","Bench Mob","Red Zone Rats","The Audibles","Sunday Scaries","Taco Tuesday","Pocket Rockets","Waiver Wire Warriors"];
export const LEAGUE = "L1";
export const MY_ROSTER_ID = "3";

export function createTradeMock() {
  const players = [];
  const rosters = [];
  for (let t = 1; t <= 12; t++) {
    const ids = [];
    for (let k = 0; k < 16; k++) {
      const i = (t - 1) * 16 + k;
      const id = String(4000 + i);
      const pos = POS[k];
      players.push({
        player_id: id, name: NAMES[i % NAMES.length] + (i >= NAMES.length ? ` ${["Jr.","II","III","IV","V"][Math.floor(i / NAMES.length) - 1] ?? ""}` : ""),
        position: pos, team: NFL[i % 12], age: 21 + (i * 7) % 13,
        status: "Active", injury_status: i % 17 === 3 ? "Questionable" : i % 29 === 7 ? "Out" : null, tier: k < 3 ? "elite" : k < 8 ? "starter" : "depth",
        score: Math.max(60, Math.round(9000 - i * 44)), overall_rank: i + 1, position_rank: k + 1, rank_unavailable_reason: null, opportunity_label: null, overall_rating: 90 - Math.floor(i / 4),
      });
      ids.push(id);
    }
    rosters.push({ roster_id: t, owner_id: "o" + t, players: ids });
  }
  const picks = [];
  for (let t = 1; t <= 12; t++) for (const [season, round] of [[2027, 1], [2027, 2], [2027, 3], [2028, 1], [2028, 2], [2028, 3]]) {
    picks.push({ pick_id: `${season}-${round}-${t}`, label: `${season} Round ${round}`, score: 3000 - round * 700 - (season - 2027) * 200, season, round, original_roster_id: String(t), owner_roster_id: String(t), original_team_name: TEAM_NAMES[t - 1], owner_team_name: TEAM_NAMES[t - 1], pick_tier: null, projected_pick_range: round === 1 ? "Early-mid" : null });
  }
  const profiles = Object.fromEntries(TEAM_NAMES.map((n, i) => [String(i + 1), { team_name: n, owner_name: "Mgr " + (i + 1), username: "mgr" + (i + 1), avatar_id: "", avatar_url: "", roster_id: i + 1, owner_id: "o" + (i + 1) }]));
  const verdict = {
    band: "Fair", ui_verdict: "FAIR", confidence: "Medium", rationale: "Both sides give up similar value.", value_summary: "", roster_summary: "", strategy_summary: "", risk_summary: "", counter_guidance: "",
    fit_total: 0, value_delta: 120, tone: "fair", counter_action: null, alternate_packages: [],
  };
  const calls = [];
  const mock = (method, path, query, body) => {
    calls.push(`${method} ${path}`);
    const ok = (b) => ({ status: 200, body: b });
    if (path.endsWith("/my-roster")) return ok({ ok: true, roster: rosters[2], reason: "" });
    if (path.endsWith("/rankings")) return ok({ ok: true, players });
    if (path.endsWith("/draft-picks")) return ok({ ok: true, picks, reason: "" });
    if (path.endsWith("/rosters")) return ok({ ok: true, rosters });
    if (path.endsWith("/team-profiles")) return ok({ ok: true, profiles });
    if (path.endsWith("/idp/values")) return ok({ ok: true, idp: false, players: [] });
    if (path.endsWith("/trade-analyzer") && method === "POST") return ok({ ok: true, verdict, reason: "" });
    if (path.endsWith("/players/search")) return ok({ ok: true, players: players.filter((p) => !query.q || p.name.toLowerCase().includes(String(query.q).toLowerCase())).slice(0, 25) });
    return null;
  };
  mock.calls = calls;
  mock.players = players;
  return mock;
}
