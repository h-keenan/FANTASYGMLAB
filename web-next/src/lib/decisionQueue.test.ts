import { describe, expect, it } from "vitest";

import {
  buildDecisionQueue,
  DECISION_VISIBLE_LIMIT,
  decisionSummaryParts,
  isWaiverDay,
  nextGameLine,
  seeAllLabel,
  type DecisionInput,
  type DecisionItem,
  type DecisionMove,
} from "@/lib/decisionQueue";

const MON = new Date(2026, 10, 9, 12);
const TUE = new Date(2026, 10, 10, 12);

const player = (id: string, name: string) => ({ player_id: id, name, position: "RB", team: "BUF", tier: "starter", injury_label: "" });
const hole = (id: string, name: string, reason: "bye_week" | "ruled_out" = "bye_week", gain = 4.1): DecisionMove => ({
  start: player(`s-${id}`, `Sub ${name}`),
  over: player(id, name),
  over_reason: reason,
  gain,
  locked: false,
});
const item = (over: Partial<DecisionItem> = {}): DecisionItem => ({
  category: "top_priority",
  headline: "Something",
  reason: "Because",
  destination: "gm_plan",
  route_player_id: "",
  route_player_name: "",
  route_player_position: "",
  route_player_team: "",
  route_player_tier: "",
  route_player_score: null,
  route_player_injury_status: "",
  mentioned_players: [],
  presentation: null,
  ...over,
});
const base = (over: Partial<DecisionInput> = {}): DecisionInput => ({ now: MON, moves: [], thisWeek: null, items: [], tradeWindow: null, ...over });
const win = (deadline: number, current: number, passed = false) => ({ trade_deadline_week: deadline, current_week: current, trade_deadline_passed: passed });

describe("decision queue: each decision type", () => {
  it("lineup holes become one lineup decision with player rows and the swap gain", () => {
    const q = buildDecisionQueue(base({ moves: [hole("p1", "Rob Stevenson"), hole("p2", "Al Out", "ruled_out", 2)] }));
    expect(q.all).toHaveLength(1);
    const d = q.all[0];
    expect(d.kind).toBe("lineup");
    expect(d.players.map((p) => p.id)).toEqual(["p1", "p2"]);
    expect(d.players[0].stat).toEqual({ value: "+4.1", label: "GAIN" });
    expect(d.players[0].note).toContain("On bye this week");
    expect(d.impact).toBe(6.1);
    expect(d.primary).toEqual({ label: "Fix lineup", target: "matchup" });
  });

  it("falls back to the this-week lineup risk row when the matchup has no moves", () => {
    const q = buildDecisionQueue(
      base({ thisWeek: { week: 6, next_action: null, rows: [{ key: "lineup", status: "Out", tone: "risk", headline: "Lineup has a hole", why: "A starter is out", cta_label: "Fix", route: "matchup", player_id: "" }] } }),
    );
    expect(q.all.map((d) => d.kind)).toEqual(["lineup"]);
    expect(q.all[0].title).toBe("Lineup has a hole");
  });

  it("open slots alone make a lineup decision", () => {
    const q = buildDecisionQueue(base({ openSlots: 2 }));
    expect(q.all[0].kind).toBe("lineup");
    expect(q.all[0].title).toBe("2 open slots");
  });

  it("a trade deadline this week or next is a decision; 2+ weeks out, passed or absent is not", () => {
    expect(buildDecisionQueue(base({ tradeWindow: win(10, 10) })).all[0].urgency).toBe(88);
    expect(buildDecisionQueue(base({ tradeWindow: win(10, 9) })).all[0].urgency).toBe(78);
    expect(buildDecisionQueue(base({ tradeWindow: win(10, 8) })).all).toHaveLength(0);
    expect(buildDecisionQueue(base({ tradeWindow: win(10, 10, true) })).all).toHaveLength(0);
    expect(buildDecisionQueue(base({ tradeWindow: { trade_deadline_week: null, current_week: 3, trade_deadline_passed: false } })).all).toHaveLength(0);
  });

  it("the deadline decision carries the trade idea count and opens Trade Hub", () => {
    const q = buildDecisionQueue(base({ tradeWindow: win(10, 10), tradeIdeaCount: 2 }));
    expect(q.all[0].primary).toEqual({ label: "Review ideas", target: "trade_hub" });
    expect(q.all[0].facts).toEqual(["2 trade ideas"]);
  });

  it("an injury item is an injury decision with the player avatar data", () => {
    const q = buildDecisionQueue(base({ items: [item({ headline: "T. Hill is questionable", route_player_id: "hill", route_player_name: "Tyreek Hill", route_player_position: "WR", route_player_injury_status: "Questionable" })] }));
    expect(q.all[0].kind).toBe("injury");
    expect(q.all[0].players[0]).toMatchObject({ id: "hill", name: "Tyreek Hill", injuryStatus: "Questionable" });
  });

  it("a waiver row and a waiver item for the same player are ONE waiver decision", () => {
    const q = buildDecisionQueue(
      base({
        items: [item({ headline: "Claim D. Mooney", destination: "waivers", route_player_id: "moo", route_player_name: "Dee Mooney", route_player_position: "WR" })],
        thisWeek: { week: 6, next_action: null, rows: [{ key: "waiver", status: "Add", tone: "waiver", headline: "Waiver add", why: "WR3 is thin", cta_label: "Open", route: "waivers", player_id: "moo" }] },
      }),
    );
    expect(q.all.filter((d) => d.kind === "waiver")).toHaveLength(1);
    expect(q.all[0].players.map((p) => p.id)).toEqual(["moo"]);
    expect(q.all[0].primary).toEqual({ label: "Claim", target: "waivers", playerId: "moo" });
  });

  it("waiver urgency rises on Tuesday and Wednesday", () => {
    const items = [item({ destination: "waivers", route_player_id: "a", route_player_name: "A B" })];
    expect(buildDecisionQueue(base({ items, now: MON })).all[0].urgency).toBe(62);
    expect(buildDecisionQueue(base({ items, now: TUE })).all[0].urgency).toBe(74);
    expect(isWaiverDay(TUE)).toBe(true);
    expect(isWaiverDay(MON)).toBe(false);
  });

  it("draft events: a live draft outranks everything, a scheduled one is a normal decision", () => {
    const live = buildDecisionQueue(
      base({ moves: [hole("p1", "Rob")], thisWeek: { week: null, rows: [], next_action: { headline: "Your draft is live", why: "On the clock", cta_label: "Join draft", route: "live_draft" } } }),
    );
    expect(live.all.map((d) => d.kind)).toEqual(["live_draft", "lineup"]);
    const sched = buildDecisionQueue(base({ thisWeek: { week: null, rows: [], next_action: { headline: "Prep your draft", why: "Draft is Sunday", cta_label: "Open Draft Center", route: "draft_center" } } }));
    expect(sched.all[0].kind).toBe("draft");
    const trade = buildDecisionQueue(base({ thisWeek: { week: null, rows: [], next_action: { headline: "x", why: "y", cta_label: "z", route: "trade_hub" } } }));
    expect(trade.all).toHaveLength(0);
  });

  it("other top-priority items become item decisions; trade ideas stay out of the queue", () => {
    const q = buildDecisionQueue(
      base({
        items: [
          item({ headline: "Review your IR spot", reason: "Free a roster spot", destination: "my_team" }),
          item({ headline: "Top trade", presentation: { trade_package: {} }, destination: "trade_hub" }),
          item({ category: "watch", headline: "Watch only" }),
        ],
      }),
    );
    expect(q.all.map((d) => d.title)).toEqual(["Review your IR spot"]);
    expect(q.all[0].primary.label).toBe("Open");
  });
});

describe("decision queue: dedupe, order, cap", () => {
  it("the lineup issue appears once: injury alerts about lineup-hole players are dropped", () => {
    const q = buildDecisionQueue(
      base({
        moves: [hole("p1", "Rob Stevenson", "ruled_out")],
        thisWeek: { week: 6, next_action: null, rows: [{ key: "lineup", status: "Out", tone: "risk", headline: "Lineup hole", why: "x", cta_label: "Fix", route: "matchup", player_id: "" }] },
        items: [
          item({ headline: "Stevenson is out", route_player_id: "p1", route_player_name: "Rob Stevenson", route_player_injury_status: "Out" }),
          item({ headline: "2 injured starters", mentioned_players: [{ player_id: "p1" }] }),
        ],
      }),
    );
    expect(q.all.map((d) => d.kind)).toEqual(["lineup"]);
  });

  it("the same alert title never appears twice", () => {
    const q = buildDecisionQueue(base({ items: [item({ headline: "IR spot (+2 more)" }), item({ headline: "ir spot" })] }));
    expect(q.all).toHaveLength(1);
  });

  it("orders by impact within the same urgency, and the order does not depend on input order", () => {
    const items = [item({ headline: "Low", route_player_score: 10 }), item({ headline: "High", route_player_score: 80 }), item({ headline: "Mid", route_player_score: 40 })];
    const a = buildDecisionQueue(base({ items }));
    const b = buildDecisionQueue(base({ items: [...items].reverse() }));
    expect(a.all.map((d) => d.title)).toEqual(["High", "Mid", "Low"]);
    expect(b.all.map((d) => d.title)).toEqual(["High", "Mid", "Low"]);
    expect(a.all.map((d) => d.rank)).toEqual([1, 2, 3]);
  });

  it("full ordering across types", () => {
    const q = buildDecisionQueue(
      base({
        moves: [hole("p1", "Rob")],
        tradeWindow: win(9, 9),
        thisWeek: { week: 9, rows: [], next_action: { headline: "Draft", why: "w", cta_label: "Open", route: "draft_center" } },
        items: [
          item({ headline: "Misc" }),
          item({ headline: "Hurt", route_player_id: "h", route_player_name: "Hal Hurt", route_player_injury_status: "Out" }),
          item({ headline: "Add", destination: "waivers", route_player_id: "w", route_player_name: "Wes Wire" }),
        ],
      }),
    );
    expect(q.all.map((d) => d.kind)).toEqual(["lineup", "deadline", "injury", "waiver", "draft", "item"]);
  });

  it("caps the visible decisions at 3 and keeps the rest for See all (N)", () => {
    const items = Array.from({ length: 5 }, (_, i) => item({ headline: `Item ${i}`, route_player_score: 50 - i }));
    const q = buildDecisionQueue(base({ items }));
    expect(DECISION_VISIBLE_LIMIT).toBe(3);
    expect(q.visible).toHaveLength(3);
    expect(q.rest).toHaveLength(2);
    expect(q.total).toBe(5);
    expect(seeAllLabel(q, false)).toBe("See all (5)");
    expect(seeAllLabel(q, true)).toBe("Show top 3");
    expect(q.next).toBe(q.all[0]);
  });

  it("no See all when everything fits", () => {
    expect(seeAllLabel(buildDecisionQueue(base({ items: [item({ headline: "One" })] })), false)).toBeNull();
  });
});

describe("decision queue: empty state and gating", () => {
  it("empty queue says nothing needs you and names the next game", () => {
    const q = buildDecisionQueue(base({ nextGame: { week: 7, opponentName: "Mock Mavericks" } }));
    expect(q.total).toBe(0);
    expect(q.next).toBeNull();
    expect(q.empty).toEqual({ title: "Nothing needs you this week", detail: "Next up: Week 7 vs Mock Mavericks" });
  });

  it("next game line only states what is known", () => {
    expect(nextGameLine({ week: null, opponentName: "X" })).toBe("Next up: vs X");
    expect(nextGameLine({ week: 3, opponentName: "" })).toBe("Next up: Week 3");
    expect(nextGameLine(null)).toBeNull();
    expect(buildDecisionQueue(base()).empty?.detail).toBeNull();
  });

  it("a non-empty queue has no empty state", () => {
    expect(buildDecisionQueue(base({ openSlots: 1 })).empty).toBeNull();
  });

  it("Free accounts with hidden moves get the Pro line; Pro and nothing-hidden do not", () => {
    expect(buildDecisionQueue(base({ entitlement: { isPremium: false, hiddenCount: 2 } })).proUpsell).toEqual({ hidden: 2 });
    expect(buildDecisionQueue(base({ entitlement: { isPremium: true, hiddenCount: 2 } })).proUpsell).toBeNull();
    expect(buildDecisionQueue(base({ entitlement: { isPremium: false, hiddenCount: 0 } })).proUpsell).toBeNull();
    expect(buildDecisionQueue(base()).proUpsell).toBeNull();
  });

  it("summary parts carry the title and the one-line reason", () => {
    const q = buildDecisionQueue(base({ moves: [hole("p1", "Rob")] }));
    const parts = decisionSummaryParts(q.all[0]);
    expect(parts[0]).toMatchObject({ key: "title", strong: true, tone: "danger" });
    expect(parts[0].text).toBe("1 starter can't play (bye or out)");
    expect(parts[1].text).toBe("Best swap: start Sub Rob over Rob (+4.1 pts)");
  });
});
