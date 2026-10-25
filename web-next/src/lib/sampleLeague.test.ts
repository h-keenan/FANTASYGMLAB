import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import { sampleDashboardResponse, sampleTeamRankings } from "./sampleDashboard";
import {
  SAMPLE_DASHBOARD_ITEMS,
  SAMPLE_PULSE_TEAMS,
  SAMPLE_ROSTER,
  SAMPLE_THIS_WEEK_ROWS,
  SAMPLE_TRADE,
  sampleTradeVerdict,
} from "./sampleLeague";

describe("sampleLeague", () => {
  it("computes a deterministic verdict from summed values", () => {
    const verdict = sampleTradeVerdict(SAMPLE_TRADE);
    expect(verdict.giveTotal).toBe(92);
    expect(verdict.getTotal).toBe(90);
    expect(verdict.label).toBe("Fair");
    expect(sampleTradeVerdict({ ...SAMPLE_TRADE, get: [{ ...SAMPLE_TRADE.get[0], value: 99 }] }).label).toBe("Favors you");
    expect(sampleTradeVerdict({ ...SAMPLE_TRADE, get: [{ ...SAMPLE_TRADE.get[0], value: 10 }] }).tone).toBe("danger");
  });

  it("has unique player ids", () => {
    const ids = [...SAMPLE_ROSTER, ...SAMPLE_TRADE.get].map((p) => p.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("has a sample Dashboard with one top priority, watch items and labelled sample reasoning", () => {
    expect(SAMPLE_DASHBOARD_ITEMS.filter((i) => i.category === "top_priority")).toHaveLength(1);
    expect(SAMPLE_DASHBOARD_ITEMS.some((i) => i.category === "watch")).toBe(true);
    expect(SAMPLE_DASHBOARD_ITEMS.every((i) => /sample/i.test(i.reason))).toBe(true);
    expect(SAMPLE_THIS_WEEK_ROWS.every((r) => /sample/i.test(r.why))).toBe(true);
    expect(SAMPLE_PULSE_TEAMS.length).toBeGreaterThan(2);
  });

  it("maps the sample Dashboard onto the real response shape without player ids", async () => {
    const data = sampleDashboardResponse();
    expect(data.this_week?.week).toBe(6);
    expect(data.items.every((i) => i.route_player_id === "" && i.mentioned_players.length === 0)).toBe(true);
    expect(data.team_snapshot?.power_rank).toBe(3);
    expect(data.entitlement.hidden_count).toBe(0);
    expect((await sampleTeamRankings()).teams.length).toBeGreaterThan(2);
  });

  it("stays identical to the mobile copy", () => {
    const web = readFileSync(resolve(__dirname, "sampleLeague.ts"), "utf8");
    const mobile = readFileSync(resolve(__dirname, "../../../mobile/src/lib/sampleLeague.ts"), "utf8");
    expect(mobile).toBe(web);
  });
});
