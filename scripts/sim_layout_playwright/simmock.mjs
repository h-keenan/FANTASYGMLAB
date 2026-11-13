// Mocked /v1/sim/games API for Fantasy Sim screenshots. Shapes follow docs/fantasy-sim-api.md.
const NAMES = ["Jaxon Moore","Devin Carter","Malik Ross","Tyrese Boone","Caleb Hunt","Elijah Stone","Noah Banks","Austin Pike","Marcus Lane","Dominic Reyes","Trevor Quinn","Isaiah Webb","Julian Cross","Brandon Holt","Cooper Vance","Rashad Ellis","Landon Frost","Micah Shaw","Xavier Doyle","Terrell Nash","Colton Rhodes","Derrick Moss","Gavin Price","Jerome Tate","Wesley Burke","Anthony Cole","Darius Webb","Kendrick Hale","Preston Lowe","Ronnie Fox","Silas Grant","Theo Barrett","Victor Dunn","Zane Mercer","Andre Keller","Bryce Larkin","Corey Wells","Damon Pryor","Elias Voss","Felix Ward"];
const NFL = ["KC","SF","BUF","PHI","DAL","MIA","CIN","DET","BAL","LAR","GB","MIN","NYJ","SEA","ATL","HOU"];
const TEAMS = ["Gridiron Goats","Blitz Brigade","Dynasty Dogs","Fourth & Long","Hail Marys","Bench Mob","Red Zone Rats","The Audibles","Sunday Scaries","Taco Tuesday","Pocket Rockets","Waiver Wire Warriors"];
const PERSONAS = [
  {id:"contender",label:"Contender",blurb:"Wants proven starters and pays up for them."},
  {id:"rebuilder",label:"Rebuilder",blurb:"Sells vets for youth and picks."},
  {id:"value_shark",label:"Value Shark",blurb:"Only takes deals that win on value."},
  {id:"youth",label:"Youth Hoarder",blurb:"Collects players under 24."},
  {id:"specialist",label:"Position Specialist",blurb:"Over-drafts one position."},
  {id:"passive",label:"Passive",blurb:"Follows ADP and sets lineups late."},
  {id:"wildcard",label:"Wildcard",blurb:"Hard to predict."},
];
const POS_CYCLE = ["QB","RB","WR","RB","WR","TE","WR","RB","QB","WR","TE","RB","WR","K","RB","WR","TE","QB"];
const SLOTS = ["QB","RB","RB","WR","WR","TE","FLEX","K"];

export function makePlayers(n = 200) {
  const out = [];
  for (let i = 0; i < n; i++) {
    const pos = POS_CYCLE[i % POS_CYCLE.length];
    const base = pos === "K" ? 8 : pos === "QB" ? 19 : pos === "TE" ? 10 : 14;
    const proj = Math.max(3, base + 7 - i * 0.11);
    out.push({
      id: String(9000 + i),
      name: NAMES[i % NAMES.length] + (i >= NAMES.length ? ` ${["Jr.","II","III"][Math.floor(i / NAMES.length) - 1] ?? ""}` : ""),
      pos, team: NFL[i % NFL.length], age: 22 + (i * 7) % 12, adp: i + 1, value: Math.max(5, 96 - i * 0.7),
      value_rank: i + 1 - (((i * 7) % 13) - 6), adp_edge: ((i * 7) % 13) - 6, projection: Math.round(proj * 10) / 10, floor: Math.round(proj * 5) / 10, ceiling: Math.round(proj * 17) / 10,
      status: i % 29 === 7 ? "out" : i % 23 === 5 ? "bye" : "healthy", out_weeks: i % 29 === 7 ? 3 : 0, bye_week: 5 + (i % 9),
      last_week: Math.round(proj * 0.9 * 10) / 10, season_points: Math.round(proj * 3.4 * 10) / 10, games: 3, ppg: Math.round(proj * 10) / 10,
    });
  }
  return out;
}

export function createMock(opts = {}) {
  const players = makePlayers();
  const state = {
    status: opts.status ?? "drafting", week: opts.week ?? 0, pro: opts.pro ?? true, storage: opts.storage ?? true, enabled: opts.enabled ?? true,
    owner: {}, // pid -> team id
    pick: 0, queue: [], picks: [], claims: [], advanced: 0, lineupLocked: false,
  };
  const you = "3";
  const teams = TEAMS.map((name, i) => ({ team_id: String(i + 1), name: i + 1 === 3 ? "Zach's Squad" : name, persona_id: PERSONAS[i % 7].id, is_you: i + 1 === 3 }));
  function order(i) { const round = Math.floor(i / 12); const idx = i % 12; return round % 2 === 0 ? idx + 1 : 12 - idx; }
  const owner = (p) => state.owner[p.id];
  const row = (p) => ({ ...p, owner: owner(p) ? { type: owner(p) === you ? "you" : "ai", team_id: owner(p), name: teams[Number(owner(p)) - 1].name } : { type: "free_agent", team_id: null, name: null } });
  function assignRosters() {
    // after draft: snake assign the best 14*12 players
    const sorted = [...players];
    sorted.slice(0, 192).forEach((p, i) => { state.owner[p.id] = String(order(i)); });
  }
  if (state.status !== "drafting") assignRosters();
  const preview = () => state.pro ? null : { weeks_left: state.status === "drafting" ? 3 : Math.max(0, 4 - state.week), paywall_week: 4, paywalled: state.status !== "drafting" && state.week >= 4 };
  const env = (reason = "") => ({ ok: true, reason, is_premium: state.pro, upsell: null, preview: preview() });
  const premium = () => ({ ok: true, reason: "premium_required", is_premium: false, upsell: { title: "Keep your season going", body: "The draft and your first 3 weeks are free. Pro unlocks the rest of the season, the playoffs and your final grade." }, preview: { weeks_left: 0, paywall_week: 4, paywalled: true } });
  const roster = (tid) => players.filter((p) => state.owner[p.id] === tid).sort((a, b) => b.projection - a.projection).map(row);
  const standings = () => teams.map((t, i) => ({ rank: i + 1, team_id: t.team_id, name: t.name, owner: "Mgr " + (i + 1), is_you: t.is_you, persona_id: t.persona_id, wins: Math.max(0, 3 - (i % 4)), losses: i % 4, ties: 0, pf: 380 - i * 9.3, pa: 340 + i * 4.1, streak: i % 2 ? "W2" : "L1", seed: i < 6 ? i + 1 : null, playoff_status: i < 6 ? "in" : "out" }));
  const settings = () => ({ teams: 12, scoring: "ppr", difficulty: "normal", regular_weeks: 14, playoff_teams: 6, playoff_weeks: 3, trade_deadline_week: 10, roster_limit: 16, rounds: 14, slots: SLOTS, user_slot: 3, auto_lineup: false });
  function game() {
    const inSeason = state.status === "in_season" || state.status === "playoffs";
    return {
      id: "11111111-1111-1111-1111-111111111111", status: state.status, week: state.week,
      phase: { drafting: "draft", in_season: "regular_season", playoffs: "playoffs", complete: "complete" }[state.status], round: state.status === "playoffs" ? state.week - 14 : null,
      seed: 7, engine_version: "game-1.0.0", settings: settings(),
      you: inSeason || state.status === "complete" ? { team_id: you, name: "Zach's Squad", wins: 2, losses: 1, ties: 0, pf: 361.4, pa: 330.2, rank: 4, seed: null } : { team_id: you, name: "Zach's Squad", wins: 0, losses: 0, ties: 0, pf: 0, pa: 0, rank: null, seed: null },
      this_week: inSeason ? { week: state.week, opponent: { team_id: "7", name: "Red Zone Rats", persona_id: "passive" }, bye: false, your_projection: 121.4, opponent_projection: 117.9 } : null,
      pending: inSeason ? { claims: state.claims.length, inbox: 2, lineup_warnings: 1, roster_size: opts.overLimit ? 18 : 16, roster_limit: 16, cuts_needed: opts.overLimit ? 2 : 0 } : null,
      can_trade: inSeason && state.week <= 10, trade_deadline_week: 10, grade_letter: state.status === "complete" ? "B+" : null, created_at: "2026-11-01T00:00:00Z", updated_at: "2026-11-02T00:00:00Z",
    };
  }
  function draftState(full = true) {
    const total = 168;
    const onClockTeam = state.pick < total ? String(order(state.pick)) : null;
    const yours = []; for (let i = 0; i < total; i++) if (String(order(i)) === you) yours.push(i + 1);
    const next = yours.find((n) => n > state.pick) ?? null;
    const d = {
      status: state.pick >= total ? "complete" : "in_progress", pick_no: state.pick + 1, round: Math.floor(state.pick / 12) + 1, total_picks: total,
      on_the_clock: onClockTeam ? { team_id: onClockTeam, name: teams[Number(onClockTeam) - 1].name, is_you: onClockTeam === you } : null,
      your_pick_numbers: yours, picks_until_you: next ? next - 1 - state.pick : 0, queue: state.queue,
      your_roster: roster(you), teams,
    };
    if (full) { d.picks = state.picks; d.order = []; }
    return d;
  }
  function advanceAI() { while (state.pick < 168 && String(order(state.pick)) !== you) makePick(null); }
  function makePick(pid) {
    const tid = String(order(state.pick));
    const p = pid ? players.find((x) => x.id === pid) : players.find((x) => !state.owner[x.id]);
    state.owner[p.id] = tid;
    const pk = { pick_no: state.pick + 1, round: Math.floor(state.pick / 12) + 1, team_id: tid, player: row(p), adp: p.adp, value_over_adp: tid === you ? 3 : (state.pick % 5) - 2, auto: false };
    state.picks.push(pk); state.pick++; return pk;
  }
  if (state.status === "drafting") { state.pick = opts.pickStart ?? 2; for (let i = 0; i < state.pick; i++) { const p = players[i]; state.owner[p.id] = String(order(i)); state.picks.push({ pick_no: i + 1, round: 1, team_id: String(order(i)), player: row(p), adp: p.adp, value_over_adp: (i % 5) - 2, auto: false }); } }
  const lineup = () => {
    const mine = roster(you);
    const take = (pos, n) => mine.filter((p) => p.pos === pos).slice(0, n);
    const qb = take("QB", 1), rb = take("RB", 3), wr = take("WR", 3), te = take("TE", 1), k = take("K", 1);
    const slots = [["QB", qb[0]], ["RB", rb[0]], ["RB", rb[1]], ["WR", wr[0]], ["WR", wr[1]], ["TE", te[0]], ["FLEX", rb[2] ?? wr[2]], ["K", k[0]]].map(([slot, player]) => ({ slot, player: player ?? null }));
    let used = new Set(slots.map((s) => s.player?.id));
    const spare = mine.filter((p) => !used.has(p.id));
    for (const s of slots) if (!s.player) { const p = spare.shift(); if (p) { s.player = p; used.add(p.id); } }
    return { ...env(), week: state.week, slots, bench: mine.filter((p) => !used.has(p.id)), projected_total: 121.4, warnings: [{ code: "bye", slot: "WR", player_id: slots[3].player?.id }], roster_size: mine.length, roster_limit: 16, opponent: { team_id: "7", name: "Red Zone Rats" }, locked: false };
  };
  const recap = (week) => ({
    week, kind: "regular", round: null,
    your_game: { opponent_id: "7", opponent_name: "Red Zone Rats", your_pts: 128.4, opp_pts: 109.7, result: "win",
      starters: lineup().slots.map((s) => ({ slot: s.slot, player: s.player, pts: s.player ? Math.round(s.player.projection * 1.1 * 10) / 10 : 0, flag: s.player?.status === "bye" ? "bye" : null })),
      optimal_pts: 134.2, efficiency: 0.96 },
    scores: [], standings: standings().slice(0, 6), waivers: [{ team_id: you, name: "Zach's Squad", add: row(players[60]), drop: null, ok: true, reason: "" }],
    transactions: [], injuries: [{ player: row(players[8]), weeks: 3, team_id: you, is_yours: true }],
    mvp: { player: row(players[2]), pts: 31.2 }, bust: { player: row(players[11]), pts: 2.4 }, playoffs: null, season_complete: false, champion: null, next_week: week + 1,
  });

  // returns {status, body} or null if not a sim route
  return function handle(method, path, query, body) {
    if (!state.enabled) return { status: 404, body: { detail: "Not Found" } };
    const m = path.match(/^\/v1\/sim\/games(?:\/([^/]+))?(\/.*)?$/);
    if (!m) return null;
    const sub = m[2] ?? ""; const id = m[1];
    if (!state.storage) return { status: 200, body: { ok: true, reason: "sim_storage_unavailable", is_premium: state.pro, upsell: null, preview: null } };
    if (id === "options") return { status: 200, body: { ...env(), engine_version: "game-1.0.0", max_games: state.pro ? 3 : 1, options: { teams: { values: [8, 10, 12], default: 12 }, scoring: { values: ["ppr", "half", "std"], default: "ppr" }, difficulty: { values: ["easy", "normal", "hard"], default: "normal" }, user_slot: { min: 1, max: 12, default: null }, auto_lineup: { default: false } }, season: { regular_weeks: 14, playoff_weeks: 3, playoff_teams: 6, trade_deadline_week: 10, roster_limit: 16, draft_rounds: 14, slots: SLOTS }, personas: PERSONAS } };
    if (!id && method === "GET") return { status: 200, body: { ...env(), games: opts.noGames ? [] : [{ id: "11111111-1111-1111-1111-111111111111", seed: 7, engine_version: "game-1.0.0", settings: settings(), status: state.status, current_week: state.week, difficulty: "normal", grade_letter: state.status === "complete" ? "B+" : null, event_count: 30, created_at: "", updated_at: "" }], max_games: state.pro ? 3 : 1 } };
    if (!id && method === "POST") { return { status: 200, body: { ...env(), game: game(), draft: draftState() } }; }
    if (!sub) return method === "DELETE" ? { status: 200, body: { ...env() } } : { status: 200, body: { ...env(), game: game() } };
    if (sub === "/draft" && method === "GET") return { status: 200, body: { ...env(), draft: draftState(), available: { items: [], total: 0, page: 1, page_size: 1 }, hint: state.pick < 168 && String(order(state.pick)) === you ? { player: row(players.find((p) => !state.owner[p.id])), why: "Best available for your need: RB" } : null } };
    if (sub === "/draft/pick") { const picks = [makePick(body.player_id)]; advanceAI(); const d = draftState(false); const done = state.pick >= 168; if (done) { state.status = "in_season"; state.week = 1; } return { status: 200, body: { ...env(), picks, draft: d, completed: done, recap: done ? { teams: teams.map((t, i) => ({ team_id: t.team_id, name: t.name, grade: ["A","B+","A-","B","C+","B-","C","B+","A-","C","B","D+"][i], starter_projection: 140 - i * 3.2, is_you: t.is_you })), your_team: { team_id: you, name: "Zach's Squad", grade: "A-", starter_projection: 132.4, best_pick: { player: row(players[12]) }, worst_pick: { player: row(players[30]) } } } : null, game: game() } }; }
    if (sub === "/draft/auto") { const picks = []; while (state.pick < 168) { if (String(order(state.pick)) === you) picks.push(makePick(null)); else makePick(null); } state.status = "in_season"; state.week = 1; return { status: 200, body: { ...env(), picks, draft: draftState(false), completed: true, recap: { teams: teams.map((t, i) => ({ team_id: t.team_id, name: t.name, grade: "B", starter_projection: 140 - i * 3.2, is_you: t.is_you })), your_team: { team_id: you, name: "Zach's Squad", grade: "B+", starter_projection: 130, best_pick: null, worst_pick: null } }, game: game() } }; }
    if (sub === "/draft/queue") { state.queue = body.player_ids; return { status: 200, body: { ...env(), queue: state.queue } }; }
    if (sub === "/players" ) {
      let items = players.map(row);
      if (query.status === "available") items = items.filter((p) => p.owner.type === "free_agent");
      if (query.status === "mine") items = items.filter((p) => p.owner.type === "you");
      if (query.pos) items = items.filter((p) => p.pos === query.pos);
      if (query.q) items = items.filter((p) => p.name.toLowerCase().includes(query.q.toLowerCase()));
      const sort = query.sort || "projection"; const key = { projection: (p) => -p.projection, value: (p) => -p.value, adp: (p) => p.adp, age: (p) => p.age, name: (p) => p.name, last_week: (p) => -p.last_week, season: (p) => -p.season_points }[sort];
      items.sort((a, b) => (key(a) < key(b) ? -1 : 1));
      const size = Number(query.page_size || 25), page = Number(query.page || 1);
      return { status: 200, body: { ...env(), items: items.slice((page - 1) * size, page * size), total: items.length, page, page_size: size } };
    }
    let mm;
    if ((mm = sub.match(/^\/players\/(.+)$/))) { const p = players.find((x) => x.id === mm[1]); return { status: 200, body: { ...env(), player: row(p), weeks: Array.from({ length: 6 }, (_, i) => ({ week: state.week + i || 1 + i, projection: p.projection + ((i * 7) % 5) - 2, floor: p.floor, ceiling: p.ceiling + i, bye: i === 3, out: false })), history: [{ week: 1, points: 18.2, stats: null }, { week: 2, points: 9.4, stats: null }, { week: 3, points: 21.1, stats: null }], news: [{ week: 3, text: `${p.name} saw a season-high in snaps and looks to be the lead option.` }] } }; }
    if ((mm = sub.match(/^\/teams\/(.+)$/))) return { status: 200, body: { ...env(), team_id: mm[1], players: roster(mm[1]) } };
    if (sub === "/lineup" && method === "GET") return { status: 200, body: lineup() };
    if (sub === "/lineup" && method === "PUT") return { status: 200, body: lineup() };
    if (sub === "/lineup/auto") return { status: 200, body: lineup() };
    if (sub === "/waivers" && method === "POST") { const p = players.find((x) => x.id === body.add); const claim = { id: "c" + (state.claims.length + 1), add: row(p), drop: null, start_slot: body.start_slot }; state.claims.push(claim); return { status: 200, body: { ...env(), claim_id: claim.id, claim, claims: state.claims } }; }
    if (sub === "/cut") return { status: 200, body: { ...env(), roster: roster(you) } };
    if (sub === "/trades/preview" || sub === "/trades") {
      const decision = body.get.length > 1 ? "decline" : body.give.length > 1 ? "counter" : "accept";
      const verdict = { decision, reason_code: "fits_need", reason: decision === "accept" ? "They need a RB and this fills it." : decision === "counter" ? "They want a bit more value." : "That asks for too much.", chips: ["needs RB", "fair value"], counter: decision === "counter" ? { give: body.give.map((i) => row(players.find((p) => p.id === i))), get: body.get.map((i) => row(players.find((p) => p.id === i))) } : null };
      return { status: 200, body: { ...env(), verdict, executed: sub === "/trades" && decision === "accept", trade: null } };
    }
    if (sub === "/inbox") return { status: 200, body: { ...env(), items: [{ id: "o1", type: "trade_offer", from: { team_id: "7", name: "Red Zone Rats", persona_id: "passive" }, you_give: [row(players[9])], you_get: [row(players[20])], message: "Your WR depth looks strong. Interested in a swap?", expires_week: state.week }] } };
    if (sub === "/advance") {
      if (!state.pro && state.week >= 3 && opts.paywallOnAdvance) return { status: 200, body: premium() };
      state.advanced++; const week = state.week; state.week++;
      if (opts.finishOnAdvance) { state.status = "complete"; return { status: 200, body: { ...env(), recap: { ...recap(week), season_complete: true, champion: you, next_week: null }, also_played: [], replayed: false, game: game() } }; }
      return { status: 200, body: { ...env(), recap: recap(week), also_played: [], replayed: false, game: game() } };
    }
    if (sub === "/home") {
      const P = (i) => row(players[i]);
      const mine = lineup();
      const rows = mine.slots.map((s, i) => ({ slot: s.slot, you: s.player, opp: row(players[20 + i]) }));
      const rec = (w, l) => ({ wins: w, losses: l, ties: 0, pf: 361.4, pa: 330.2, rank: 4 });
      return { status: 200, body: { ...env(), week: state.week, phase: "regular_season",
        matchup: { week: state.week, bye: false, kind: "regular", opponent: { team_id: "7", name: "Red Zone Rats", persona_id: "passive", record: rec(2, 1), persona: PERSONAS[5] }, you_record: rec(2, 1), you_projection: 121.4, opp_projection: 117.9, win_prob: 0.62, rows, you_flagged: 1, opp_flagged: 1 },
        checklist: [
          { id: "lineup", label: "Set your lineup", detail: "1 starter slot needs attention (out, on bye or empty).", done: false, target: "team", severity: "danger" },
          { id: "offers", label: "Answer trade offers", detail: "2 offers waiting in your inbox.", done: false, target: "trades", severity: "accent" },
          { id: "waivers", label: "Check the wire", detail: "A RB could add 7.5 pts this week.", done: false, target: "players", severity: "warning" },
          { id: "byes", label: "Plan for byes", detail: "WR1 is on bye in Week 7.", done: true, target: "team", severity: "ok" },
        ],
        inbox: { count: 2, open: true, items: [0, 1].map((k) => ({ id: "o" + k, from: { team_id: "7", name: "Red Zone Rats", persona_id: "passive" }, you_give: [P(9 + k)], you_get: [P(20 + k)], expires_week: state.week })) },
        waiver_suggestions: [60, 61, 62].map((i, k) => ({ player: P(i), gain_now: 7.5 - k, gain_ros: 1.2, reasons: ["Covers Hurt Harry (out): +7.5 pts this week", "Rising snap share"], drop: k === 0 ? P(70) : null, covers: P(8), for_slot: "RB1" })),
        bye_alerts: [3, 5].map((i, k) => ({ week: 7 + k, weeks_away: 3 + k, slot: "WR", pos_label: "WR" + (k + 1), player: P(i), covered: k === 1, covered_by: k === 1 ? P(30) : null, replacements: [P(31), P(32)], message: "Your WR" + (k + 1) + " is on bye in Week " + (7 + k) + ". Look at the wire for a fill-in." })),
        injuries: [8, 11, 14].map((i) => ({ player: { ...P(i), status: "out", out_weeks: 3 }, out_weeks: 3, starting: i === 8, note: "Hurt in Week 3" })),
        hot_cold: { hot: [1, 2, 3, 4, 5].map((i) => ({ player: P(i), last_week: 30.2 - i, delta: 9.1 - i, avg: 22 })), cold: [6, 7, 8, 9, 10].map((i) => ({ player: P(i), last_week: 3.2 + i, delta: -9.1 + i, avg: 15 })), wire: [60, 61, 62, 63, 64].map((i) => ({ player: P(i), last_week: 20 - (i - 60), delta: 6, avg: 12 })) },
        standings: { rows: standings(), playoff_spots: 6, games_left: 11, your_rank: 4, margin: 1, in_playoffs: true },
        league: { recent: [{ week: 3, type: "trade", team_id: "5", text: "Dynasty Dogs traded Marcus Lane to Hail Marys for Trevor Quinn.", players: [] }, { week: 3, type: "waiver", team_id: "9", text: "Taco Tuesday added Wesley Burke.", players: [] }, { week: 3, type: "waiver", team_id: "2", text: "Blitz Brigade added Felix Ward.", players: [] }], spotlight: { week: 3, text: "Dynasty Dogs and Hail Marys swapped starters.", headline: "Blockbuster swap", team_a: { team_id: "5", name: "Dynasty Dogs" }, team_b: { team_id: "6", name: "Hail Marys" }, players: [] } } } };
    }
    if (sub === "/league") return { status: 200, body: { ...env(), standings: standings(), schedule: Array.from({ length: 14 }, (_, w) => ({ week: w + 1, kind: "regular", games: [0, 1, 2, 3, 4, 5].map((g) => ({ home: String(g * 2 + 1), away: String(g * 2 + 2), home_pts: w < 3 ? 100 + g * 4 + w : null, away_pts: w < 3 ? 95 + g * 3 : null, winner: w < 3 ? String(g * 2 + 1) : null })) })), transactions: [{ week: 3, type: "trade", team_id: "5", text: "Dynasty Dogs traded Marcus Lane to Hail Marys for Trevor Quinn." }, { week: 3, type: "waiver", team_id: "9", text: "Taco Tuesday added Wesley Burke." }], teams: teams.map((t, i) => ({ team_id: t.team_id, name: t.name, owner: "Mgr " + (i + 1), persona: PERSONAS[i % 7], is_you: t.is_you, power_rank: i + 1, avg_age: 25.4 + i * 0.2 })), playoffs: null } };
    if (sub === "/result") return { status: 200, body: { ...env(), result: makeResult(players, standings, you, opts.variant || "champion", row) } };
    if (sub === "/revert-week") return { status: 200, body: { ...env(), game: game(), reverted: 2 } };
    return { status: 404, body: { detail: "no mock" } };
  };
}

function makeResult(players, standings, you, variant, row) {
  const br = (i) => { const p = players[i]; return { id: p.id, headshot_id: null, name: p.name, pos: p.pos, team: p.team }; };
  const champ = variant === "champion";
  const rows = standings().map((s, i) => ({ ...s, playoff_result: (champ ? i === 2 : i === 0) ? "champion" : i === 3 && !champ ? "runner_up" : i < 6 && i !== 2 ? (i % 2 ? "semifinal" : "lost_round_1") : i === 2 ? (champ ? "champion" : "missed") : "missed" }));
  return {
    champion: champ ? { team_id: you, name: "Zach's Squad" } : { team_id: "1", name: "Gridiron Goats" },
    final_standings: rows,
    grade: { letter: champ ? "A-" : "D+", score: champ ? 88.1 : 41.2, summary: { record: champ ? "11-3" : "5-9", finish: champ ? 2 : 9, points_rank: champ ? 1 : 7, playoff_result: champ ? "champion" : "missed", lineup_efficiency: 0.93, luck_wins: 0.8, draft_grade: "B" },
      components: [{ key: "record", label: "Record and seeding", score: champ ? 88 : 30, weight: 0.35 }, { key: "points", label: "Points scored", score: champ ? 95 : 55, weight: 0.2 }, { key: "playoffs", label: "Playoff result", score: champ ? 100 : 0, weight: 0.25 }, { key: "lineup", label: "Lineup efficiency", score: champ ? 80 : 20, weight: 0.1 }, { key: "moves", label: "Draft and roster moves", score: 62, weight: 0.1 }] },
    user: { team_id: you, wins: champ ? 11 : 5, losses: champ ? 3 : 9, playoff_result: champ ? "champion" : "missed" },
    decisions_that_mattered: [
      { kind: "trade", week: 5, title: "Week 5 trade: sent Marcus Lane, got Jaxon Moore", detail: "That deal helped your season (+1 wins, +3.2 points per game, Champion vs Semifinal without it).", impact: { season_value: 1.1, wins: 1, points_per_game: 3.2, playoff_result_with: champ ? "champion" : "missed", playoff_result_without: "semifinal" }, players: [{ ...br(2), role: "get" }, { ...br(9), role: "give" }] },
      { kind: "waiver", week: 3, title: "Week 3 waiver: added Wesley Burke, dropped Trevor Quinn", detail: "That pickup barely moved the needle on your season (+0 wins, +0.3 points per game).", impact: { season_value: 0.1, wins: 0, points_per_game: 0.3, playoff_result_with: "missed", playoff_result_without: "missed" }, players: [{ ...br(60), role: "add" }, { ...br(21), role: "drop" }] },
      { kind: "lineup", week: 2, title: "Week 2: 49.9 points sat on your bench", detail: "In hindsight a different lineup was worth 49.9 more points that week (Jalen Coker scored 31.3 on your bench while Parker Washington scored 3.4 in your lineup).", impact: { season_value: -0.83 }, players: [{ ...br(31), role: "bench", pts: 31.3 }, { ...br(33), role: "started", pts: 3.4 }] },
    ],
    draft: { grade: "B" },
    review: {
      team_count: 12,
      season_stats: [{ key: "ppg", label: "Points per game", value: "112.4" }, { key: "high", label: "Best week", value: "168", sub: "Week 1", tone: "good" }, { key: "low", label: "Worst week", value: "64.8", sub: "Week 11", tone: "bad" }, { key: "streak", label: "Longest win streak", value: "6", tone: "good" }, { key: "bench", label: "Points left on bench", value: "259.3", tone: "bad" }, { key: "injuries", label: "Injuries to your players", value: "7", tone: "bad" }, { key: "mvp", label: "Season MVP", value: "387.9", sub: "pts in your lineup", player: br(2), tone: "good" }],
      awards: [
        { key: "best_trade", kind: "trade", tone: "good", label: "Best trade", headline: "Week 5 trade", players: [{ ...br(2), role: "get" }, { ...br(9), role: "give" }], week: 5, delta: { value: 61.4, unit: "pts" }, detail: "Got Malik Ross (212.4 pts after the deal) for Dominic Reyes (151 pts).", outcome: "Won the deal" },
        { key: "worst_trade", kind: "trade", tone: "bad", label: "Worst trade", headline: "Week 9 trade", players: [{ ...br(14), role: "get" }, { ...br(5), role: "give" }], week: 9, delta: { value: -38.2, unit: "pts" }, detail: "Got a player who scored less than the one you sent.", outcome: "Lost the deal" },
        { key: "best_waiver", kind: "waiver", tone: "good", label: "Best waiver pickup", headline: "Week 3 pickup", players: [{ ...br(60), role: "add" }, { ...br(21), role: "drop" }], week: 3, delta: { value: 88.1, unit: "pts" }, detail: "Scored 141.2 points from week 3 on. The dropped player scored 53.1.", outcome: "Great find" },
        { key: "best_pick", kind: "draft", tone: "good", label: "Best draft pick", headline: "Round 10 pick", players: [{ ...br(40), role: "pick" }], delta: { value: 17, unit: "adp" }, detail: "Pick 118 (round 10), ADP 101. Scored 126.1 points over 16 games.", outcome: "Steal" },
        { key: "worst_pick", kind: "draft", tone: "bad", label: "Worst draft pick", headline: "Round 2 pick", players: [{ ...br(12), role: "pick" }], delta: { value: -9, unit: "adp" }, detail: "Pick 22 (round 2), ADP 31. Scored 60 points over 8 games.", outcome: "Reach" },
        { key: "boom", kind: "boom", tone: "good", label: "Biggest boom", headline: "Week 5", players: [{ ...br(4), role: "boom" }], week: 5, delta: { value: 47.8, unit: "pts" }, detail: "Your top single-game score of the season: 47.8 points.", outcome: "Boom" },
        { key: "bust", kind: "bust", tone: "bad", label: "Biggest bust", headline: "Week 14", players: [{ ...br(11), role: "bust" }], week: 14, delta: { value: -18.3, unit: "pts" }, detail: "Projected for about 23.3, scored 5.0.", outcome: "Bust" },
        { key: "injury_cost", kind: "injury", tone: "bad", label: "Injury that cost the most", headline: "Missed 9 weeks", players: [{ ...br(8), role: "hurt" }], delta: { value: -108, unit: "pts" }, detail: "Averaging 12 points a game, that is about 108 points left on the sideline.", outcome: "Injured" },
      ],
      injuries: { your_injuries: 7, weeks_missed: 19, points_lost: 229.8, most_injured_team: { team_id: "11", name: "Waiver Wire Warriors", count: 20, is_you: false } },
      leaders: { league: [
        { pos: "QB", rows: [0, 8, 17].map((i, k) => ({ player: br(i), pts: 380 - k * 22, ppg: 23.8 - k, team_id: "3", team_name: k ? "Blitz Brigade" : "Zach's Squad", is_you: k === 0 })) },
        { pos: "RB", rows: [1, 3, 7].map((i, k) => ({ player: br(i), pts: 340 - k * 18, ppg: 21 - k, team_id: "4", team_name: "Dynasty Dogs", is_you: false })) },
        { pos: "WR", rows: [2, 4, 6].map((i, k) => ({ player: br(i), pts: 355 - k * 15, ppg: 22 - k, team_id: "5", team_name: "Hail Marys", is_you: false })) },
        { pos: "TE", rows: [5, 10, 16].map((i, k) => ({ player: br(i), pts: 220 - k * 20, ppg: 13 - k, team_id: "6", team_name: "Bench Mob", is_you: false })) },
        { pos: "K", rows: [13, 22].map((i, k) => ({ player: br(i), pts: 160 - k * 9, ppg: 9.4, team_id: "7", team_name: "Red Zone Rats", is_you: false })) } ],
        yours: [{ key: "pass_yd", label: "Passing yards", rows: [{ player: br(0), value: 4210 }, { player: br(8), value: 612 }] }, { key: "rec_yd", label: "Receiving yards", rows: [{ player: br(2), value: 1388 }, { player: br(4), value: 1120 }, { player: br(6), value: 804 }] }, { key: "td", label: "Touchdowns", rows: [{ player: br(2), value: 14 }, { player: br(1), value: 11 }] }] },
      games: { closest_yours: [{ week: 4, kind: "regular", home: "Zach's Squad", away: "Red Zone Rats", home_pts: 101.2, away_pts: 100.9, margin: 0.3, is_yours: true, you_won: true }, { week: 9, kind: "regular", home: "Hail Marys", away: "Zach's Squad", home_pts: 98.4, away_pts: 97.1, margin: 1.3, is_yours: true, you_won: false }],
        closest_league: [{ week: 4, kind: "regular", home: "Zach's Squad", away: "Red Zone Rats", home_pts: 101.2, away_pts: 100.9, margin: 0.3, is_yours: true, you_won: true }, { week: 6, kind: "regular", home: "Bench Mob", away: "Taco Tuesday", home_pts: 120.2, away_pts: 119.8, margin: 0.4, is_yours: false, you_won: null }] },
      rank_journey: [5, 4, 4, 2, 3, 2, 1, 1, 2, 2, 3, 2, 2, 2].map((r, i) => ({ week: i + 1, rank: r, wins: Math.floor(i * 0.75), losses: i - Math.floor(i * 0.75), ties: 0 })),
      champion_path: { team_id: you, name: champ ? "Zach's Squad" : "Gridiron Goats", is_you: champ, seed: champ ? 2 : 1, total_rounds: 3, rounds: [{ round: 1, bye: true, week: 15 }, { round: 2, week: 16, bye: false, opponent: "Hail Marys", opponent_seed: 4, pts: 131.2, opp_pts: 118.6, won: true }, { round: 3, week: 17, bye: false, opponent: "Blitz Brigade", opponent_seed: 1, pts: 141.9, opp_pts: 140.2, won: true }] },
      your_path: champ ? null : null,
    },
  };
}
