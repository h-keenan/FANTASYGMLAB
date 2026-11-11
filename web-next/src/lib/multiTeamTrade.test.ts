import { describe, expect, it } from "vitest";

import {
  addTeam,
  analysisLayout,
  analysisOrder,
  buildMatrix,
  buildShareModel,
  buildShareText,
  buildTransfers,
  builderIssue,
  formatSigned,
  isMultiTradeOk,
  lineupEffectText,
  mostHurtBanner,
  multiTradeErrorMessages,
  multiTradeFailureLines,
  removeTeam,
  shareGetsBack,
  toneSemantic,
  topReasons,
  upsertAsset,
  vetoTone,
  type BuilderAsset,
  type MultiAsset,
  type MultiTeamResult,
  type MultiTeamTradeResponse,
} from "./multiTeamTrade";

const asset = (id: string, label: string, position: string, score: number, extra: Partial<MultiAsset> = {}): MultiAsset => ({
  type: "player",
  id,
  label,
  position,
  team: "BUF",
  score,
  ...extra,
});

function team(id: string, name: string, over: Partial<MultiTeamResult>): MultiTeamResult {
  return {
    roster_id: id,
    team_name: name,
    is_perspective: id === "1",
    sends: [],
    receives: [],
    verdict: { ui_verdict: "FAIR" },
    trade_score: 0,
    market_delta: 0,
    lineup_delta: { per_week: 0 },
    tone: "fair",
    outcome: "even",
    why: [],
    veto_risk: null,
    ...over,
  };
}

const teams = (n: number): MultiTeamResult[] =>
  Array.from({ length: n }, (_, i) =>
    team(String(i + 1), `Team ${i + 1}`, {
      trade_score: 1000 - i * 400,
      market_delta: 300 - i * 150,
      sends: [asset(`s${i}`, `Sent ${i}`, "WR", 500, { to_roster_id: String(((i + 1) % n) + 1), to_team_name: `Team ${((i + 1) % n) + 1}` })],
      receives: [asset(`r${i}`, `Got ${i}`, i % 2 ? "RB" : "QB", 900, { from_roster_id: String(((i + n - 1) % n) + 1), from_team_name: `Team ${((i + n - 1) % n) + 1}` })],
    }),
  );

const response = (n: number): MultiTeamTradeResponse => ({
  status: "ok",
  teams: teams(n),
  summary: {
    headline: "h",
    team_count: n,
    balance: { id: "lopsided", label: "Lopsided: at least one team is giving up a lot", spread: 1400, best_roster_id: "1", worst_roster_id: String(n) },
    most_hurt_roster_id: String(n),
    best_off_roster_id: "1",
    ranking: teams(n)
      .map((t, i) => ({ rank: n - i, roster_id: t.roster_id, team_name: t.team_name, trade_score: t.trade_score }))
      .sort((a, b) => a.rank - b.rank),
  },
});

describe("builder", () => {
  const a = (id: string, from: string, to: string): BuilderAsset => ({ type: "player", id, fromRosterId: from, toRosterId: to });

  it("requires 3 teams, assets, and every team involved", () => {
    expect(builderIssue(["1", "2"], [])?.code).toBe("too_few_teams");
    expect(builderIssue(["1", "2", "3"], [])?.code).toBe("no_assets");
    expect(builderIssue(["1", "2", "3"], [a("p", "1", "2")])?.code).toBe("team_not_involved");
    expect(builderIssue(["1", "2", "3"], [a("p", "1", "2"), a("q", "2", "3")])).toBeNull();
    expect(builderIssue(["1", "2", "3"], [a("p", "1", "")])?.code).toBe("unrouted");
  });

  it("caps at 6 teams and drops a removed team's assets", () => {
    expect(addTeam(["1", "2", "3", "4", "5", "6"], "7")).toHaveLength(6);
    expect(addTeam(["1"], "1")).toEqual(["1"]);
    const out = removeTeam(["1", "2", "3"], [a("p", "1", "2"), a("q", "2", "3"), a("r", "1", "3")], "2");
    expect(out.participants).toEqual(["1", "3"]);
    expect(out.assets.map((x) => x.id)).toEqual(["r"]);
  });

  it("moves an asset once and builds API transfers", () => {
    const first = upsertAsset([], a("p", "1", "2"));
    const second = upsertAsset(first, a("p", "1", "3"));
    expect(buildTransfers(second)).toEqual([{ type: "player", id: "p", from_roster_id: "1", to_roster_id: "3" }]);
  });

  it("builds a sender by receiver matrix", () => {
    const grid = buildMatrix(["1", "2", "3"], [a("p", "1", "2"), a("q", "1", "2")]);
    expect(grid["1"]["2"]).toHaveLength(2);
    expect(grid["2"]["1"]).toHaveLength(0);
  });
});

describe("errors in plain language", () => {
  it("maps each API code and keeps the server detail", () => {
    const [line] = multiTradeErrorMessages([{ code: "asset_not_owned", message: "Star QB is not on Team 2" }]);
    expect(line).toContain("no longer on the team");
    expect(line).toContain("Star QB is not on Team 2");
    expect(multiTradeErrorMessages([{ code: "weird", message: "Custom." }])).toEqual(["Custom."]);
  });

  it("prefers errors, then reason, then headline", () => {
    expect(multiTradeFailureLines({ errors: [{ code: "too_many_teams" }] })[0]).toContain("at most 6");
    expect(multiTradeFailureLines({ reason: "unsupported_platform" })[0]).toContain("Sleeper");
    expect(multiTradeFailureLines({ reason: "unavailable" })[0]).toContain("not ready");
    expect(multiTradeFailureLines({ headline: "Head" })).toEqual(["Head"]);
    expect(multiTradeFailureLines({})).toEqual(["Could not analyze this trade."]);
  });

  it("only treats status ok with teams as a result", () => {
    expect(isMultiTradeOk(response(3))).toBe(true);
    expect(isMultiTradeOk({ status: "invalid" })).toBe(false);
    expect(isMultiTradeOk(null)).toBe(false);
  });
});

describe("analysis", () => {
  it("uses a stack up to 4 teams and a ranked list from 5", () => {
    expect(analysisLayout(3)).toBe("stack");
    expect(analysisLayout(4)).toBe("stack");
    expect(analysisLayout(5)).toBe("ranked");
    expect(analysisLayout(6)).toBe("ranked");
  });

  it("keeps your team first in a stack and ranks best to worst in a list", () => {
    expect(analysisOrder(response(3)).map((t) => t.roster_id)).toEqual(["1", "2", "3"]);
    const r5 = response(5);
    r5.summary!.ranking = [
      { rank: 1, roster_id: "4", trade_score: 9 },
      { rank: 2, roster_id: "1", trade_score: 8 },
      { rank: 3, roster_id: "2", trade_score: 7 },
      { rank: 4, roster_id: "3", trade_score: 6 },
      { rank: 5, roster_id: "5", trade_score: 5 },
    ];
    expect(analysisOrder(r5).map((t) => t.roster_id)).toEqual(["4", "1", "2", "3", "5"]);
  });

  it("names the most hurt team unless the deal is balanced", () => {
    expect(mostHurtBanner(response(3)).headline).toBe("Most hurt: Team 3");
    const balanced = response(3);
    balanced.summary!.balance.id = "balanced";
    expect(mostHurtBanner(balanced).headline).toBe("No team is clearly hurt");
  });

  it("formats value, lineup and tones with fixed semantics", () => {
    expect(formatSigned(1234)).toBe("+1,234");
    expect(formatSigned(-5)).toBe("-5");
    expect(formatSigned(0)).toBe("0");
    expect(lineupEffectText({ lineup_delta: { per_week: 2.14, ros: 40 } })).toBe("+2.1 pts a week in the lineup, +40 rest of season");
    expect(lineupEffectText({ lineup_delta: { per_week: 0 } })).toBe("No change to the weekly lineup");
    expect(toneSemantic("accept")).toBe("success");
    expect(toneSemantic("counter")).toBe("warning");
    expect(toneSemantic("decline")).toBe("danger");
    expect(toneSemantic("fair")).toBe("neutral");
    expect(vetoTone("outrage")).toBe("danger");
    expect(vetoTone("fair")).toBe("success");
  });

  it("shows at most 3 reasons, flows last", () => {
    const why = [
      { factor: "flows", text: "flows" },
      { factor: "risk", text: "risk" },
      { factor: "market", text: "market" },
      { factor: "lineup", text: "lineup" },
      { factor: "posture", text: "posture" },
    ];
    expect(topReasons({ why }).map((w) => w.factor)).toEqual(["market", "lineup", "posture"]);
  });
});

describe("share model (persuasion framed)", () => {
  it("draws a flow for 3 teams and a list for 4 or more", () => {
    expect(buildShareModel(response(3)).layout).toBe("flow");
    expect(buildShareModel(response(4)).layout).toBe("list");
    expect(buildShareModel(response(6)).layout).toBe("list");
  });

  it("still prints every team's true value change as a plain number", () => {
    const model = buildShareModel(response(3));
    expect(model.teams.map((t) => t.valueChangeText)).toEqual(["+300", "+150", "0"]);
    expect(model.edges).toHaveLength(3);
  });

  it("says what a team giving up value gets back", () => {
    const giver = team("2", "Giver", {
      market_delta: -400,
      receives: [asset("a", "Thin Position Starter", "TE", 800), { type: "pick", id: "2027:1:2", label: "2027 Round 1", position: "", team: "", score: 600 }],
    });
    expect(shareGetsBack(giver)).toBe("Gets back Thin Position Starter (TE) and 2027 Round 1");
    expect(shareGetsBack({ ...giver, market_delta: 10 })).toBe("");
  });

  it("never uses scoreboard words in the share text", () => {
    const text = buildShareText(buildShareModel(response(3)), "My League");
    expect(text).toContain("3-team trade in My League");
    expect(text).toContain("Value change");
    expect(text).not.toMatch(/most hurt|loses|lopsided|decline/i);
    expect(text).toContain("Team 1 -> Team 2");
  });
});
