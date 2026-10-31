import { describe, expect, it } from "vitest";

import {
  bandTone,
  integrityReasonMessage,
  integritySummaryLine,
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
