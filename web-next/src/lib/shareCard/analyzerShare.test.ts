import { describe, expect, it } from "vitest";

import type { TradeAsset, TradeVerdict } from "@/lib/api";

import { buildAnalyzerIdea, buildPartnerPitch } from "./analyzerShare";

const verdict = {
  band: "Fair",
  ui_verdict: "COUNTER",
  confidence: "Medium",
  rationale: "Roughly even on value.",
  value_summary: "",
  roster_summary: "",
  strategy_summary: "",
  risk_summary: "",
  counter_guidance: "",
  fit_total: 0,
  value_delta: -274,
  tone: "counter",
} as TradeVerdict;

const player = (over: Partial<TradeAsset>): TradeAsset => ({ asset_type: "player", player_id: "1", name: "P", position: "QB", team: "ARI", score: 1000, ...over });
const pick = (over: Partial<TradeAsset> = {}): TradeAsset => ({ asset_type: "pick", label: "2028 Round 1", season: "2028", round: "1", score: 900, ...over });

describe("buildAnalyzerIdea", () => {
  it("fills the trade card from the on-screen analysis only", () => {
    const send = [player({ player_id: "1", score: 4400 }), pick()];
    const receive = [player({ player_id: "2", position: "WR", score: 3000 })];
    const idea = buildAnalyzerIdea({ sendAssets: send, receiveAssets: receive, verdict, partnerName: "Rival GM", partnerAvatarUrl: "https://sleepercdn.com/avatars/a" });
    expect(idea.partner_team_name).toBe("Rival GM");
    expect(idea.partner_team_avatar_url).toBe("https://sleepercdn.com/avatars/a");
    expect(idea.send_score).toBe(5300);
    expect(idea.receive_score).toBe(3000);
    expect(idea.package.send).toBe(send);
    expect(idea.package.receive).toBe(receive);
    expect(idea.value_edge_band).toBe("Fair");
    expect(idea.trade_gain).toBe(-274);
    expect(idea.confidence_label).toBe("Medium");
  });

  it("names the partner generically when All Teams is selected", () => {
    const idea = buildAnalyzerIdea({ sendAssets: [player({})], receiveAssets: [player({ player_id: "2" })], verdict, partnerName: "" });
    expect(idea.partner_team_name).toBe("Trade partner");
    expect(idea.partner_team_avatar_url).toBeNull();
  });
});

describe("buildPartnerPitch", () => {
  it("pitches a trade that favors the partner with real numbers only", () => {
    const send = [player({ name: "Star QB", position: "QB", score: 5000 })];
    const receive = [player({ player_id: "2", name: "Backup QB", position: "QB", score: 3000 })];
    const pitch = buildPartnerPitch(send, receive, "Rival GM");
    expect(pitch.headline).toBe("A trade that works for Rival GM");
    expect(pitch.lines).toEqual(["You gain 2,000 in value", "Upgrade at QB: Star QB"]);
  });

  it("calls an even trade fair and never claims a value gain", () => {
    const pitch = buildPartnerPitch([player({ score: 1000 })], [player({ player_id: "2", position: "WR", score: 980 })], "Rival GM");
    expect(pitch.lines).toEqual(["Fair value both ways"]);
  });

  it("does not claim the trade works for the partner when values favor the sender", () => {
    const pitch = buildPartnerPitch([pick({ score: 500 })], [player({ score: 4000 })], "Rival GM");
    expect(pitch.headline).toBe("Trade proposal for Rival GM");
    expect(pitch.lines.join(" ")).not.toMatch(/gain|value/i);
    expect(pitch.lines).toEqual(["Adds a 2028 Round 1 pick"]);
  });

  it("falls back to a plain headline with no partner and counts multiple picks", () => {
    const pitch = buildPartnerPitch([pick(), pick({ season: "2029" })], [], "");
    expect(pitch.headline).toBe("Trade proposal");
    expect(pitch.lines).toContain("Adds 2 draft picks");
  });

  it("shows at most three lines", () => {
    const send = [player({ name: "A", score: 5000 }), pick(), pick({ season: "2029" })];
    expect(buildPartnerPitch(send, [player({ player_id: "2", score: 100 })], "X").lines.length).toBeLessThanOrEqual(3);
  });
});
