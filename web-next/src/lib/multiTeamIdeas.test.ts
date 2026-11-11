import { describe, expect, it } from "vitest";

import {
  decodePrefill,
  encodePrefill,
  ideaAnalyzerQuery,
  ideaAsResponse,
  ideaTeamLines,
  ideasSection,
  lockedTeaserTitle,
  prefillKey,
  prefillToBuilder,
  type MultiTeamIdea,
} from "./multiTeamIdeas";
import type { MultiTransfer } from "./multiTeamTrade";

const TRANSFERS: MultiTransfer[] = [
  { type: "player", id: "4034", from_roster_id: "1", to_roster_id: "2" },
  { type: "player", id: "6794", from_roster_id: "2", to_roster_id: "3" },
  { type: "pick", id: "2027:1:3", from_roster_id: "3", to_roster_id: "1" },
];

function team(id: string, name: string, over: Record<string, unknown> = {}) {
  return {
    roster_id: id,
    team_name: name,
    is_perspective: id === "1",
    sends: [{ type: "player", id: `s${id}`, label: `Sends ${id}`, position: "RB", team: "SF", to_roster_id: "2", to_team_name: "B" }],
    receives: [{ type: "player", id: `r${id}`, label: `Gets ${id}`, position: "WR", team: "SF", from_roster_id: "3", from_team_name: "C" }],
    verdict: { ui_verdict: "Fair" },
    trade_score: 100,
    market_delta: id === "1" ? 120 : -80,
    lineup_delta: { per_week: 1.2 },
    tone: "fair",
    outcome: "even",
    why: [
      { factor: "flows", text: "flows text" },
      { factor: "need", text: `${name} fills a WR need.` },
    ],
    ...over,
  };
}

const IDEA = {
  id: "m3-abc",
  headline: "B + C: you get X, you send Y",
  teams: [team("2", "Team B"), team("1", "Team A"), team("3", "Team C", { tone: "accept", verdict: { ui_verdict: "Good for them" } })],
  flows: TRANSFERS.map((t) => ({ ...t, from_team_name: "x", to_team_name: "y" })),
  partners: [],
  user: { roster_id: "1", trade_score: 100, market_delta: 120, lineup_delta: { per_week: 1.2 }, outcome: "even" },
  summary: {},
  variant: null,
  analyzer_request: { transfers: TRANSFERS, perspective_roster_id: "1" },
} as unknown as MultiTeamIdea;

describe("prefill encoding", () => {
  it("round trips every transfer, including a pick id with colons", () => {
    const encoded = encodePrefill(TRANSFERS);
    expect(encoded).toBe("player~1~2~4034,player~2~3~6794,pick~3~1~2027:1:3");
    expect(decodePrefill(encoded)).toEqual(TRANSFERS);
  });

  it("drops malformed, duplicate, self-addressed and unknown-type entries", () => {
    const raw = ["player~1~2~a", "player~1~2~a", "bad~1~2~b", "player~1~1~c", "player~1~~d", "player~1~2~", "junk"].join(",");
    expect(decodePrefill(raw)).toEqual([{ type: "player", id: "a", from_roster_id: "1", to_roster_id: "2" }]);
    expect(decodePrefill("")).toEqual([]);
    expect(decodePrefill(null)).toEqual([]);
  });

  it("caps the number of transfers", () => {
    const many = Array.from({ length: 50 }, (_, i) => `player~1~2~p${i}`).join(",");
    expect(decodePrefill(many)).toHaveLength(36);
  });

  it("loads the builder with the viewer's team first and every asset routed", () => {
    const state = prefillToBuilder(
      [
        { type: "player", id: "a", from_roster_id: "2", to_roster_id: "3" },
        { type: "player", id: "b", from_roster_id: "3", to_roster_id: "1" },
        { type: "player", id: "c", from_roster_id: "1", to_roster_id: "2" },
      ],
      "1",
    );
    expect(state.participants).toEqual(["1", "2", "3"]);
    expect(state.assets).toContainEqual({ type: "player", id: "a", fromRosterId: "2", toRosterId: "3" });
  });

  it("keys a prefill by its content, not its order", () => {
    expect(prefillKey(TRANSFERS)).toBe(prefillKey([...TRANSFERS].reverse()));
  });

  it("builds the Analyzer link query without escaping the separators", () => {
    const query = ideaAnalyzerQuery("Dynasty Overlords", IDEA);
    expect(query).toBe("name=Dynasty+Overlords&multi=player~1~2~4034,player~2~3~6794,pick~3~1~2027:1:3");
    expect(decodePrefill(new URLSearchParams(query).get("multi"))).toEqual(TRANSFERS);
  });
});

describe("ideasSection", () => {
  it("shows ideas, a locked count for Free, and honest empty and closed states", () => {
    expect(ideasSection({ ideas: [IDEA], idea_count: 1, locked: false })).toEqual({ kind: "ideas", ideas: [IDEA] });
    expect(ideasSection({ ideas: [], idea_count: 3, locked: true })).toEqual({ kind: "locked", count: 3 });
    expect(ideasSection({ ideas: [], idea_count: 0, locked: false, reason: "no_fit" })).toMatchObject({ kind: "empty" });
    expect(ideasSection({ ideas: [], idea_count: 0, locked: false, reason: "trade_deadline_passed", message: "Closed." })).toEqual({
      kind: "closed",
      message: "Closed.",
    });
    expect(ideasSection(null).kind).toBe("empty");
  });

  it("words the locked teaser by count", () => {
    expect(lockedTeaserTitle(1)).toBe("1 three-team deal fits your league");
    expect(lockedTeaserTitle(4)).toBe("4 three-team deals fit your league");
  });
});

describe("idea card model", () => {
  it("lists the viewer first as You, with the need reason and a signed value change", () => {
    const lines = ideaTeamLines(IDEA);
    expect(lines.map((l) => l.name)).toEqual(["You", "Team B", "Team C"]);
    expect(lines[0]).toMatchObject({ isYou: true, valueChange: "+120", gets: "Gets 1", sends: "Sends 1", why: "Team A fills a WR need." });
    expect(lines[1].valueChange).toBe("-80");
    expect(lines[2].verdict).toBe("Good for them");
  });

  it("feeds the pitch card the same shape the Analyzer's results do", () => {
    const response = ideaAsResponse(IDEA);
    expect(response.teams).toHaveLength(3);
    expect(response.teams?.every((t) => t.veto_risk === null)).toBe(true);
    expect(response.flows).toHaveLength(3);
  });
});
