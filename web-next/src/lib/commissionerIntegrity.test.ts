import { describe, expect, it } from "vitest";

import {
  bandTone,
  integrityReasonMessage,
  calendarLines,
  integritySummaryLine,
  restSummary,
  splitTeams,
  type CommissionerIntegrityResponse,
  type IntegrityTeam,
} from "./commissionerIntegrity";

function team(band: IntegrityTeam["band"], id = 1): IntegrityTeam {
  return {
    roster_id: id, team_name: `T${id}`, owner_name: "o", band, band_label: band, score: 0.5, confidence: "medium",
    interpretation: "none", context: "alive", weeks: { evaluated: 5, flagged: 0, longest_streak: 0, latest_streak: 0 },
    evidence: [], innocent_explanations: [], series: [],
  };
}

function resp(teams: IntegrityTeam[], extra: Partial<CommissionerIntegrityResponse> = {}): CommissionerIntegrityResponse {
  return { ok: true, reason: "", teams, collusion: [], inactive: [], weeks_evaluated: 5, ...extra };
}

describe("commissioner integrity presentation", () => {
  it("maps bands to the fixed semantic tones", () => {
    expect(bandTone("fine")).toBe("success");
    expect(bandTone("worth_a_look")).toBe("warning");
    expect(bandTone("strong")).toBe("danger");
    expect(bandTone("not_enough_data")).toBe("muted");
  });

  it("splits flagged teams from the rest and summarises calmly", () => {
    const teams = [team("strong", 1), team("fine", 2), team("worth_a_look", 3), team("not_enough_data", 4)];
    const { flagged, rest } = splitTeams(teams);
    expect(flagged.map((t) => t.roster_id)).toEqual([1, 3]);
    expect(rest.map((t) => t.roster_id)).toEqual([2, 4]);
    expect(integritySummaryLine(resp(teams))).toBe("After 5 weeks: 2 teams worth a look. These are prompts to check, not conclusions.");
    expect(integritySummaryLine(resp([team("fine")]))).toContain("No team stands out");
  });

  it("explains every empty-state reason, with an honest fallback", () => {
    expect(integrityReasonMessage("not_enough_weeks")).toContain("three completed");
    expect(integrityReasonMessage("something_new")).toContain("not available");
  });
});

describe("restSummary", () => {
  it("is one line when nobody is flagged", () => {
    const teams = Array.from({ length: 12 }, (_, i) => team("fine", i + 1));
    expect(restSummary(teams, 0)).toBe("All 12 teams look fine this week");
  });
  it("counts the others when some are flagged or too early", () => {
    const teams = [team("strong", 1), team("fine", 2), team("fine", 3), team("not_enough_data", 4)];
    expect(restSummary(teams, 1)).toBe("2 other teams look fine this week; 1 without enough weeks yet");
    expect(restSummary([team("worth_a_look", 1), team("fine", 2)], 1)).toBe("1 other team looks fine this week");
    expect(restSummary([team("strong", 1)], 1)).toBe("");
  });
});

describe("calendarLines", () => {
  const base = { trade_deadline_week: 11, current_week: 8, trade_deadline_passed: false, weeks_to_deadline: 3, deadline_phase: "open" as const, playoff_week_start: 15, regular_season_weeks: 14, in_season: true };
  it("shows the deadline, weeks left and playoff start", () => {
    expect(calendarLines(base)).toEqual(["Week 8 now", "Trade deadline: after week 11 (3 weeks left)", "Playoffs start week 15"]);
  });
  it("handles last call, passed and no deadline", () => {
    expect(calendarLines({ ...base, weeks_to_deadline: 0, deadline_phase: "final_week" })[1]).toContain("last call");
    expect(calendarLines({ ...base, deadline_phase: "passed", trade_deadline_passed: true })[1]).toContain("passed");
    expect(calendarLines({ ...base, trade_deadline_week: null, deadline_phase: "none", playoff_week_start: null })).toEqual(["Week 8 now", "No trade deadline set"]);
    expect(calendarLines(null)).toEqual([]);
  });
});
