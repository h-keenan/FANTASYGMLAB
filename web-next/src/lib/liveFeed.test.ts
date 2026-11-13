import { beforeEach, describe, expect, it } from "vitest";

import {
  MAX_FEED_EVENTS,
  deriveStatPieces,
  diffSnapshots,
  feedKey,
  groupFeedByGame,
  liveFeedStore,
  mergeFeed,
  snapshotFromMatchup,
  type FeedEvent,
} from "./liveFeed";
import { midGameMatchup } from "./matchupMidGame.fixture";

const texts = (prev: Record<string, number> | null, next: Record<string, number>) =>
  deriveStatPieces(prev, next).map((piece) => piece.text);

describe("stat-delta event derivation", () => {
  it("rushing TD with yards", () => {
    expect(texts({ rush_att: 10, rush_yd: 50 }, { rush_att: 11, rush_yd: 54, rush_td: 1 })).toEqual(["rushing TD, 4 yds"]);
  });
  it("receiving and passing TDs", () => {
    expect(texts({ rec: 3, rec_yd: 30 }, { rec: 4, rec_yd: 52, rec_td: 1 })).toEqual(["receiving TD, 22 yds"]);
    expect(texts({ pass_yd: 100 }, { pass_yd: 135, pass_td: 1 })).toEqual(["passing TD, 35 yds"]);
  });
  it("field goal, extra point, interception, fumble lost", () => {
    expect(texts({ fgm: 1 }, { fgm: 2, xpm: 1 })).toEqual(["field goal", "extra point"]);
    expect(texts({}, { pass_int: 1 })).toEqual(["interception thrown"]);
    expect(texts({ fum_lost: 0 }, { fum_lost: 1 })).toEqual(["fumble lost"]);
  });
  it("reception plus yards delta without a TD", () => {
    expect(texts({ rec: 4, rec_yd: 40 }, { rec: 5, rec_yd: 52 })).toEqual(["catch, 12 yds"]);
    expect(texts({ rec: 4, rec_yd: 40 }, { rec: 6, rec_yd: 70 })).toEqual(["2 catches, 30 yds"]);
  });
  it("defense plays and no change", () => {
    expect(texts({ sack: 1 }, { sack: 2, int: 1 })).toEqual(["interception", "sack"]);
    expect(texts({ rec: 1 }, { rec: 1 })).toEqual([]);
  });
});

describe("snapshot diffing", () => {
  const snap = (tick: number) => snapshotFromMatchup(midGameMatchup(tick));

  it("no events on the first snapshot or before games start", () => {
    expect(diffSnapshots(null, snap(0), 1000)).toEqual([]);
    expect(snapshotFromMatchup({ game_state: "pregame", my_team: { has_live_data: true, real_starters: [] } }).size).toBe(0);
  });

  it("derives one event per changed player with points, detail and game", () => {
    const events = diffSnapshots(snap(0), snap(1), 2000);
    const barkley = events.find((event) => event.name === "Saquon Barkley")!;
    expect(barkley.points).toBeCloseTo(2.1);
    expect(barkley.side).toBe("mine");
    expect(barkley.gameLabel).toBe("DAL @ PHI");
    expect(barkley.detail).toBe("2 rushes, 9 yds");
    expect(barkley.approx).toBe(false);
    const aubrey = events.find((event) => event.name === "Brandon Aubrey")!;
    expect(aubrey.detail).toBe("field goal");
    expect(aubrey.approx).toBe(false);
    expect(aubrey.major).toBe(true);
    expect(events.every((event) => event.at === 2000)).toBe(true);
    // Unchanged players produce nothing.
    expect(events.find((event) => event.name === "CeeDee Lamb")).toBeUndefined();
  });

  it("labels merged events approximate", () => {
    const before = snap(0);
    const after = new Map(before);
    const cur = after.get("mine:7035")!;
    after.set("mine:7035", { ...cur, points: (cur.points ?? 0) + 4, stats: { ...(cur.stats ?? {}), fgm: 3, xpm: 3 } });
    const [event] = diffSnapshots(before, after, 7);
    expect(event.detail).toBe("2 field goals; extra point");
    expect(event.approx).toBe(true);
  });

  it("falls back to a points-only approximate event when no stats are available", () => {
    const before = snap(0);
    const after = new Map(before);
    const cur = after.get("mine:6786")!;
    after.set("mine:6786", { ...cur, points: (cur.points ?? 0) + 2.5, stats: null });
    const [event] = diffSnapshots(before, after, 5);
    expect(event.detail).toBe("yardage / other scoring");
    expect(event.approx).toBe(true);
    const down = new Map(before);
    down.set("mine:6786", { ...cur, points: (cur.points ?? 0) - 1, stats: null });
    expect(diffSnapshots(before, down, 6)[0].detail).toBe("scoring correction");
  });

  it("merges newest first, de-duplicates and caps at 50", () => {
    const mk = (n: number): FeedEvent => ({
      id: `e${n}`, at: n, playerId: "1", name: "P", position: "RB", team: "X", side: "mine", points: 1,
      detail: "d", approx: false, major: false, gameKey: "A-B", gameLabel: "A @ B",
    });
    let feed: FeedEvent[] = [];
    for (let i = 0; i < 70; i += 1) feed = mergeFeed(feed, [mk(i)]);
    expect(feed).toHaveLength(MAX_FEED_EVENTS);
    expect(feed[0].id).toBe("e69");
    expect(mergeFeed(feed, [mk(69)])).toHaveLength(MAX_FEED_EVENTS);
  });

  it("groups by game with status from the current snapshot", () => {
    const events = diffSnapshots(snap(0), snap(1), 3000);
    const groups = groupFeedByGame(events, snap(1));
    const phi = groups.find((group) => group.label === "DAL @ PHI")!;
    expect(phi.status).toMatch(/^Live ~Q[1-4]$/);
    expect(phi.events.length).toBeGreaterThan(1);
  });
});

describe("polling integration (store fed by successive payloads)", () => {
  beforeEach(() => liveFeedStore.reset());

  it("baseline poll yields nothing, later polls accumulate events and notify subscribers", () => {
    const key = feedKey("123", 10);
    let notified = 0;
    const off = liveFeedStore.subscribe(() => (notified += 1));
    expect(liveFeedStore.ingest(key, midGameMatchup(0), 1000)).toEqual([]);
    expect(liveFeedStore.events(key)).toHaveLength(0);
    expect(liveFeedStore.ingest(key, midGameMatchup(0), 2000)).toEqual([]); // same payload re-polled
    const second = liveFeedStore.ingest(key, midGameMatchup(1), 3000);
    expect(second.length).toBeGreaterThan(0);
    liveFeedStore.ingest(key, midGameMatchup(2), 4000);
    expect(liveFeedStore.events(key)[0].at).toBe(4000);
    expect(notified).toBeGreaterThanOrEqual(2);
    // A different league/week has its own feed.
    expect(liveFeedStore.events(feedKey("999", 10))).toHaveLength(0);
    off();
  });
});
