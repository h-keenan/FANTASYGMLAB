import { execFileSync } from "node:child_process";
import path from "node:path";
import { describe, expect, it } from "vitest";

import { canOpenTeam, teamDisplayName, teamLinkInteractive, teamOpenLabel, TEAM_TAP_MIN } from "@/lib/teamTap";

describe("team tap rule", () => {
  it("opens only with a league and a roster", () => {
    expect(canOpenTeam({ leagueId: "L1", rosterId: 4 })).toBe(true);
    expect(canOpenTeam({ leagueId: "L1", rosterId: "0" })).toBe(true);
    expect(canOpenTeam({ leagueId: "L1", rosterId: null })).toBe(false);
    expect(canOpenTeam({ leagueId: "", rosterId: 4 })).toBe(false);
    expect(canOpenTeam(null)).toBe(false);
  });

  it("a team's own page stays plain (a tap would be a no-op)", () => {
    expect(teamLinkInteractive({ leagueId: "L1", rosterId: 4 }, true)).toBe(false);
    expect(teamLinkInteractive({ leagueId: "L1", rosterId: 4 }, false)).toBe(true);
  });

  it("labels and minimum target", () => {
    expect(teamOpenLabel("Just Win")).toBe("Open Just Win team sheet");
    expect(teamOpenLabel("  ")).toBe("Open team sheet");
    expect(teamDisplayName(null)).toBe("Team");
    expect(TEAM_TAP_MIN).toBeGreaterThanOrEqual(44);
  });

  it("the source guard passes (scripts/check_team_tap.mjs)", () => {
    const script = path.resolve(__dirname, "../../../scripts/check_team_tap.mjs");
    expect(execFileSync("node", [script], { encoding: "utf8", stdio: "pipe" })).toContain("passed");
  });
});
