import { execFileSync } from "node:child_process";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { describe, expect, it } from "vitest";

import { canOpenTeam, teamDisplayName, teamLinkInteractive, teamOpenLabel, TEAM_TAP_MIN } from "@/lib/teamTap";

const SCRIPT = path.resolve(__dirname, "../../../scripts/check_team_tap.mjs");

// vite cannot import a repo-root script, so the guard's own functions run in a node child process.
function guard(expr: string): unknown {
  const code = `import * as g from ${JSON.stringify(pathToFileURL(SCRIPT).href)}; console.log(JSON.stringify(${expr}));`;
  return JSON.parse(execFileSync("node", ["--input-type=module", "-e", code], { encoding: "utf8" }));
}
const scan = (src: string) => guard(`g.scanSource(${JSON.stringify(src)})`) as { raw: boolean; linked: boolean };

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
    expect(execFileSync("node", [SCRIPT], { encoding: "utf8", stdio: "pipe" })).toContain("passed");
  });

  describe("guard behaviour", () => {
    it("flags a bare team name and a bare avatar, but not the shared component's own children", () => {
      expect(scan("<span>{team.team_name}</span>").raw).toBe(true);
      expect(scan("<TeamAvatar avatarUrl={a} name={n} />").raw).toBe(true);
      expect(scan("<TeamNameLink leagueId={l} rosterId={r} name={n}>{team.team_name}</TeamNameLink>").raw).toBe(false);
      expect(scan("<TeamNameLink a={1} />\n<span>{team.team_name}</span>").raw).toBe(true);
    });

    it("an exemption mark needs a real reason and covers only its own spot", () => {
      expect(scan("{/* team-tap-exempt: a pick'em choice, tapping selects the winner */}\n<TeamAvatar name={n} />").raw).toBe(false);
      expect(scan("{/* team-tap-exempt: x */}\n<TeamAvatar name={n} />").raw).toBe(true);
    });

    it("a stale allowlist entry fails", () => {
      const root = path.resolve(__dirname, "../../..");
      const allow = { "web-next/src/components/Button.tsx": "stale reason entry" };
      const errors = guard(`g.run(${JSON.stringify(root)}, ${JSON.stringify(allow)})`) as string[];
      expect(errors.some((e) => e.includes("Button.tsx") && e.includes("remove it"))).toBe(true);
    });
  });
});
