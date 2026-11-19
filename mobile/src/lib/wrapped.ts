// Season Wrapped: the card deck the server builds (modules/sim/game_wrapped.py for the Fantasy Sim, modules/wrapped_real.py for a real
// league) turned into display views, share text and a share-image model. Pure and import-free: web and the app keep byte-identical
// copies (scripts/check_lib_twins.mjs), so the cards say the same thing on both.

export type WrappedTone = "good" | "neutral" | "warm";

export interface WrappedPlayer {
  id: string;
  headshot_id: string | null;
  name: string;
  pos: string;
  team: string;
}

export interface WrappedCard {
  id: string;
  eyebrow: string;
  title: string;
  sub: string | null;
  pro: boolean;
  locked: boolean;
  // The server owns each card's data shape; the views below read it defensively and drop what is missing.
  data: Record<string, unknown> | null;
}

export interface WrappedDeck {
  kind: "sim" | "real";
  partial: boolean;
  season_label: string;
  team_name: string;
  cards: WrappedCard[];
}

export interface WrappedRow {
  label: string;
  value: string;
}

export interface WrappedBlock {
  label: string;
  badge: string | null;
  hero: string;
  unit: string | null;
  sub: string | null;
  tone: WrappedTone;
}

export interface WrappedTradeSide {
  grade: string;
  week: number;
  got: WrappedPlayer[];
  sent: WrappedPlayer[];
  net: string;
}

export interface WrappedDots {
  player: WrappedPlayer;
  beat: boolean[];
  tally: string;
  caption: string;
}

export type WrappedView =
  | { kind: "locked"; teaser: string }
  | { kind: "hero"; player: WrappedPlayer | null; hero: string; unit: string | null; chip: string | null; chipTone: WrappedTone; rows: WrappedRow[]; foot: string | null; second: WrappedPlayer | null; secondLabel: string | null }
  | { kind: "blocks"; blocks: WrappedBlock[]; rows: WrappedRow[]; miss: WrappedPlayer | null; missLine: string | null }
  | { kind: "dots"; items: WrappedDots[] }
  | { kind: "trades"; sides: WrappedTradeSide[] }
  | { kind: "luck"; actual: number; expected: number; max: number; chip: string; actualLabel: string; expectedLabel: string }
  | { kind: "journey"; ranks: number[]; teams: number; peak: string; note: string }
  | { kind: "grade"; overall: string; subs: { label: string; letter: string }[] }
  | { kind: "persona"; name: string; glyph: string; lines: string[]; runnerUp: string | null };

export const WRAPPED_LOCKED_COPY: Record<string, string> = {
  trades: "Your best and worst trade, graded, with the track record behind them.",
  steal: "Your best value pick, measured against what it cost you.",
};

/** "Jalen Pruitt" -> "J. Pruitt"; suffixes and one-word names are kept whole. */
export function wrappedShortName(name: string | null | undefined): string {
  const parts = String(name ?? "").trim().split(/\s+/).filter(Boolean);
  if (parts.length < 2) return parts[0] ?? "";
  const suffix = /^(jr\.?|sr\.?|ii|iii|iv|v)$/i;
  const last = suffix.test(parts[parts.length - 1]) && parts.length > 2 ? `${parts[parts.length - 2]} ${parts[parts.length - 1]}` : parts[parts.length - 1];
  return `${parts[0][0].toUpperCase()}. ${last}`;
}

export function wrappedNum(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

export function wrappedFmt(value: unknown, digits = 1): string {
  const n = wrappedNum(value);
  return n === null ? "-" : n.toFixed(digits);
}

export function wrappedSigned(value: unknown, digits = 1): string {
  const n = wrappedNum(value);
  if (n === null) return "-";
  return `${n > 0 ? "+" : n < 0 ? "-" : ""}${Math.abs(n).toFixed(digits)}`;
}

export function wrappedOrdinal(n: number): string {
  const v = n % 100;
  const suffix = v >= 11 && v <= 13 ? "th" : ({ 1: "st", 2: "nd", 3: "rd" } as Record<number, string>)[n % 10] ?? "th";
  return `${n}${suffix}`;
}

/** Green for an A or B, plain for the rest: a grade is never shown in red. */
export function wrappedGradeTone(letter: string): WrappedTone {
  const first = (letter || "").charAt(0).toUpperCase();
  return first === "A" || first === "B" ? "good" : first === "C" ? "warm" : "neutral";
}

function rec(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function player(value: unknown): WrappedPlayer | null {
  const p = rec(value);
  if (typeof p.id !== "string" || typeof p.name !== "string") return null;
  return { id: p.id, headshot_id: typeof p.headshot_id === "string" ? p.headshot_id : null, name: p.name, pos: typeof p.pos === "string" ? p.pos : "", team: typeof p.team === "string" ? p.team : "" };
}

function players(value: unknown): WrappedPlayer[] {
  return Array.isArray(value) ? value.map(player).filter((p): p is WrappedPlayer => p !== null) : [];
}

function pill(p: WrappedPlayer | null): string {
  return p ? [p.pos, p.team].filter(Boolean).join(" · ") : "";
}

export function wrappedPlayerLine(p: WrappedPlayer | null): string {
  return p ? `${wrappedShortName(p.name)}${pill(p) ? ` ${pill(p)}` : ""}` : "";
}

/** Defensive parse of the /wrapped body's deck; null when it is missing or has nothing to show. */
export function normalizeWrappedDeck(raw: unknown): WrappedDeck | null {
  const d = rec(raw);
  if (!Array.isArray(d.cards)) return null;
  const cards: WrappedCard[] = [];
  for (const item of d.cards) {
    const c = rec(item);
    if (typeof c.id !== "string") continue;
    cards.push({
      id: c.id,
      eyebrow: typeof c.eyebrow === "string" ? c.eyebrow : "",
      title: typeof c.title === "string" ? c.title : "",
      sub: typeof c.sub === "string" ? c.sub : null,
      pro: c.pro === true,
      locked: c.locked === true,
      data: c.data && typeof c.data === "object" ? (c.data as Record<string, unknown>) : null,
    });
  }
  if (!cards.length) return null;
  return {
    kind: d.kind === "real" ? "real" : "sim",
    partial: d.partial === true,
    season_label: typeof d.season_label === "string" ? d.season_label : "",
    team_name: typeof d.team_name === "string" ? d.team_name : "",
    cards,
  };
}

function weekLabel(week: unknown): string {
  const n = wrappedNum(week);
  return n === null ? "" : `Wk ${n}`;
}

/** What a card draws, with every number already formatted. */
export function wrappedView(card: WrappedCard): WrappedView {
  if (card.locked || !card.data) return { kind: "locked", teaser: WRAPPED_LOCKED_COPY[card.id] ?? "Part of Pro." };
  const d = card.data;
  switch (card.id) {
    case "intro":
      return { kind: "hero", player: null, hero: String(d.record ?? "-"), unit: null, chip: typeof d.outcome === "string" ? d.outcome : null, chipTone: "good", rows: [], foot: "Swipe for the highs, the lows and the moves that mattered.", second: null, secondLabel: null };
    case "mvp": {
      const over = wrappedNum(d.over_proj);
      const best = rec(d.best);
      const bestWeek = wrappedNum(best.week);
      const rows: WrappedRow[] = [{ label: "Points per game", value: wrappedFmt(d.ppg) }];
      if (wrappedNum(best.pts) !== null) rows.push({ label: "Best game", value: `${wrappedFmt(best.pts)}${bestWeek !== null ? ` in Wk ${bestWeek}` : ""}` });
      if (wrappedNum(d.share) !== null) rows.push({ label: "Share of your points", value: `${Math.round(Number(d.share))}% of your points` });
      return { kind: "hero", player: player(d.player), hero: wrappedFmt(d.pts), unit: "pts", chip: over === null ? null : `${wrappedSigned(over)} vs projection`, chipTone: "good", rows, foot: null, second: null, secondLabel: null };
    }
    case "bust":
      return { kind: "hero", player: player(d.player), hero: wrappedSigned(d.over_proj), unit: "pts", chip: "vs projection", chipTone: "neutral", rows: [{ label: "Projected", value: wrappedFmt(d.projected) }, { label: "Actual", value: wrappedFmt(d.actual) }, { label: "Why", value: String(d.why ?? "") }], foot: null, second: null, secondLabel: null };
    case "weeks": {
      const mk = (label: string, raw: unknown, tone: WrappedTone): WrappedBlock => {
        const w = rec(raw);
        const opp = typeof w.opponent === "string" && w.opponent ? `vs ${w.opponent}` : null;
        const result = w.opp_pts == null ? null : Number(w.pts) > Number(w.opp_pts) ? "Win" : Number(w.pts) < Number(w.opp_pts) ? "Loss" : "Tie";
        return { label, badge: [result, weekLabel(w.week)].filter(Boolean).join(" · ") || null, hero: wrappedFmt(w.pts), unit: "pts", sub: opp, tone };
      };
      return { kind: "blocks", blocks: [mk("Best week", d.best, "good"), mk("Worst week", d.worst, "neutral")], rows: [], miss: null, missLine: null };
    }
    case "steal": {
      const round = wrappedNum(d.round);
      const pick = wrappedNum(d.pick);
      return { kind: "hero", player: player(d.player), hero: wrappedSigned(d.over_cost), unit: "pts over cost", chip: round !== null ? `Round ${round} pick` : null, chipTone: "good", rows: [{ label: "Cost", value: round !== null && pick !== null ? `Round ${round}, pick ${pick}` : "-" }, { label: "Season points", value: wrappedFmt(d.pts) }], foot: null, second: null, secondLabel: null };
    }
    case "consistency": {
      const mk = (raw: unknown, caption: string): WrappedDots | null => {
        const r = rec(raw);
        const p = player(r.player);
        if (!p || !Array.isArray(r.beat)) return null;
        return { player: p, beat: r.beat.map(Boolean), tally: `${r.beat_count ?? 0} of ${r.games ?? r.beat.length}`, caption };
      };
      const cons = mk(d.consistent, "Rarely let you down. Filled = beat projection");
      const roll = mk(d.rollercoaster, `${wrappedFmt(rec(d.rollercoaster).swing)} pt weekly swing. Filled = beat projection`);
      return { kind: "dots", items: [cons, roll].filter((x): x is WrappedDots => x !== null) };
    }
    case "trades": {
      const mk = (raw: unknown): WrappedTradeSide | null => {
        const t = rec(raw);
        if (typeof t.grade !== "string") return null;
        return { grade: t.grade, week: Number(t.week) || 0, got: players(t.got), sent: players(t.sent), net: `${wrappedSigned(t.net)} pts net` };
      };
      return { kind: "trades", sides: [mk(d.best), mk(d.worst)].filter((x): x is WrappedTradeSide => x !== null) };
    }
    case "waiver": {
      const dropped = player(d.dropped);
      return { kind: "hero", player: player(d.player), hero: wrappedSigned(d.net), unit: "pts", chip: "after the pickup", chipTone: "good", rows: [], foot: null, second: dropped, secondLabel: dropped ? "Dropped" : null };
    }
    case "close": {
      const lost = rec(d.lost_by);
      const won = rec(d.won_by);
      const blocks: WrappedBlock[] = [];
      if (wrappedNum(lost.margin) !== null) blocks.push({ label: "Lost by", badge: weekLabel(lost.week), hero: wrappedFmt(lost.margin), unit: null, sub: null, tone: "neutral" });
      if (wrappedNum(won.margin) !== null) blocks.push({ label: "Won by", badge: weekLabel(won.week), hero: wrappedFmt(won.margin), unit: null, sub: null, tone: "good" });
      const rows: WrappedRow[] = [{ label: "Bench points left", value: `${wrappedFmt(d.bench_pts)} pts` }];
      const miss = rec(d.miss);
      const mp = player(miss.player);
      const missLine = mp ? `${weekLabel(miss.week)} · ${wrappedFmt(miss.pts)} on the bench${wrappedNum(miss.proj) !== null ? `, ${wrappedFmt(Number(miss.pts) - Number(miss.proj))} from the starter` : ""}` : null;
      return { kind: "blocks", blocks, rows, miss: mp, missLine };
    }
    case "luck": {
      const actual = Number(d.actual_wins) || 0;
      const expected = Number(d.expected_wins) || 0;
      const diff = Number(d.diff) || 0;
      return { kind: "luck", actual, expected, max: Math.max(actual, expected, Number(d.games) || 0, 1), chip: `${wrappedSigned(diff)} wins vs expected`, actualLabel: "Actual wins", expectedLabel: "Expected wins from your points" };
    }
    case "journey": {
      const ranks = Array.isArray(d.ranks) ? d.ranks.map(Number).filter((n) => Number.isFinite(n)) : [];
      const best = ranks.length ? Math.min(...ranks) : 0;
      return { kind: "journey", ranks, teams: Number(d.teams) || Math.max(...ranks, 12), peak: best ? `Peaked at ${wrappedOrdinal(best)}` : "", note: "League rank after each week" };
    }
    case "grade": {
      const subs = Array.isArray(d.subs) ? d.subs.map((s) => ({ label: String(rec(s).label ?? ""), letter: String(rec(s).letter ?? "-") })) : [];
      return { kind: "grade", overall: String(d.overall ?? "-"), subs };
    }
    case "persona":
      return { kind: "persona", name: String(d.name ?? ""), glyph: String(d.glyph ?? "swap"), lines: Array.isArray(d.lines) ? d.lines.map(String) : [], runnerUp: typeof d.runner_up === "string" ? `Runner-up: ${d.runner_up}` : null };
    default:
      return { kind: "locked", teaser: "" };
  }
}

export interface WrappedShareModel {
  eyebrow: string;
  title: string;
  sub: string | null;
  headline: string;
  unit: string | null;
  chip: string | null;
  rows: WrappedRow[];
  players: WrappedPlayer[];
  seasonLabel: string;
  teamName: string;
}

/** The one-card share image's content (the web Satori card and the app's captured card both draw this). */
export function wrappedShareModel(card: WrappedCard, deck: Pick<WrappedDeck, "season_label" | "team_name">): WrappedShareModel {
  const view = wrappedView(card);
  const base = { eyebrow: card.eyebrow, title: card.title, sub: card.sub, unit: null as string | null, chip: null as string | null, rows: [] as WrappedRow[], players: [] as WrappedPlayer[], seasonLabel: deck.season_label, teamName: deck.team_name };
  switch (view.kind) {
    case "hero":
      return { ...base, headline: view.hero, unit: view.unit, chip: view.chip, rows: view.rows, players: [view.player, view.second].filter((p): p is WrappedPlayer => p !== null) };
    case "blocks":
      return { ...base, headline: view.blocks.map((b) => b.hero).join(" / "), rows: [...view.blocks.map((b) => ({ label: b.label, value: `${b.hero}${b.unit ? ` ${b.unit}` : ""}${b.badge ? ` (${b.badge})` : ""}` })), ...view.rows], players: view.miss ? [view.miss] : [] };
    case "dots":
      return { ...base, headline: view.items.map((i) => wrappedShortName(i.player.name)).join(" vs "), rows: view.items.map((i) => ({ label: wrappedShortName(i.player.name), value: i.tally })), players: view.items.map((i) => i.player) };
    case "trades":
      return { ...base, headline: view.sides.map((s) => s.grade).join(" / "), rows: view.sides.map((s) => ({ label: `Wk ${s.week} trade`, value: `${s.grade} · ${s.net}` })) };
    case "luck":
      return { ...base, headline: `${view.actual}`, unit: "wins", chip: view.chip, rows: [{ label: view.actualLabel, value: String(view.actual) }, { label: view.expectedLabel, value: wrappedFmt(view.expected) }] };
    case "journey":
      return { ...base, headline: view.ranks.length ? `${wrappedOrdinal(view.ranks[0])} to ${wrappedOrdinal(view.ranks[view.ranks.length - 1])}` : "", chip: view.peak || null };
    case "grade":
      return { ...base, headline: view.overall, unit: "overall", rows: view.subs.map((s) => ({ label: s.label, value: s.letter })) };
    case "persona":
      return { ...base, headline: view.name, rows: view.lines.map((l) => ({ label: "", value: l })), chip: view.runnerUp };
    default:
      return { ...base, headline: "" };
  }
}

export function wrappedShareText(model: WrappedShareModel): string {
  const hero = [model.headline, model.unit].filter(Boolean).join(" ");
  const lines = [`${model.title}${model.sub ? `: ${model.sub}` : ""}`, hero + (model.chip ? ` (${model.chip})` : ""), ...model.rows.map((r) => (r.label ? `${r.label}: ${r.value}` : r.value))];
  return [...lines.filter((l) => l.trim()), "", `${model.teamName ? `${model.teamName}, ` : ""}${model.seasonLabel}`.trim(), "See yours on FantasyDesk."].join("\n");
}

/** Stable share-cache key for a card's content. */
export function wrappedShareKey(model: WrappedShareModel): string {
  return JSON.stringify([model.eyebrow, model.headline, model.unit, model.chip, model.rows, model.players.map((p) => p.id), model.teamName]);
}
