import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Source-scan guard, like lib/playerAvatarRule.test.ts for players: a Fantasy Sim team is ONLY ever rendered through the shared
 * team identity template (components/SimTeamIdentity.tsx on web and in the app: SimTeamIdentity = logo + name, SimTeamLogo = the
 * logo at a size-table slot, SimTeamLink = the tappable identity). docs/ui-patterns.md, "Team identity (Fantasy Sim)".
 * Fails when a sim component
 *   - imports the real-league TeamAvatar (initials circle) for a sim team,
 *   - mounts SimCrest directly (use SimTeamLogo / SimTeamIdentity) or gives a team component a raw pixel `size={N}`,
 *   - wraps a team name in a truncating element (a name wraps; lib/simTeamIdentity.ts fit ladder),
 *   - prints a team name in a file that never uses the template (explicit TEXT_ONLY allowlist below).
 */
const WEB = path.resolve(__dirname, "../components");
const APP = path.resolve(__dirname, "../../../mobile/src/components");

const files = (dir: string) => readdirSync(dir).filter((f) => /^Sim.*\.tsx$/.test(f) && !/\.test\./.test(f)).map((f) => path.join(dir, f));
const strip = (src: string) => src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");

const TEAM_NAME_EXPR = String.raw`\{[^{}]*?(?:team_name|teamName|team\.name|opponent_name|from\.name|owner_name)\b[^{}]*\}`;
const TRUNCATING_WEB = new RegExp(String.raw`<(?:span|div|p|a|button|h\d)\b[^>]*\b(?:truncate|text-ellipsis|line-clamp-\d)\b[^>]*>\s*${TEAM_NAME_EXPR}`, "g");
const TRUNCATING_APP = new RegExp(String.raw`<(?:AppText|Text)\b[^>]*numberOfLines=\{\d\}[^>]*>\s*${TEAM_NAME_EXPR}`, "g");
const NAME_IN_JSX = new RegExp(String.raw`>\s*${TEAM_NAME_EXPR}`);

/** Components that never show a team's logo on purpose: text-only contexts (share-card PNG text, sentences, sr-only labels). */
const TEXT_ONLY: Record<string, string> = {
  "SimGameRecap.tsx": "the full-details recap table prints names through SimTeamLink rows; sentence fragments only",
  "SimDraftGrid.tsx": "draft grid column header: compact text cell, the pick cell carries the logo",
};

describe("sim teams always render through the team identity template", () => {
  for (const [label, dir] of [["web", WEB], ["app", APP]] as const) {
    const list = files(dir).filter((f) => !/SimTeamIdentity\.tsx$|SimCrest\.tsx$/.test(f));
    it(`${label}: no real-league TeamAvatar for a sim team`, () => {
      expect(list.filter((f) => /\bTeamAvatar\b/.test(strip(readFileSync(f, "utf8")))).map((f) => path.basename(f))).toEqual([]);
    });
    it(`${label}: SimCrest is mounted only by SimTeamIdentity (use SimTeamLogo)`, () => {
      expect(list.filter((f) => /\bSimCrest\b/.test(strip(readFileSync(f, "utf8")))).map((f) => path.basename(f))).toEqual([]);
    });
    it(`${label}: team components take a size-table slot, never a raw pixel number`, () => {
      const hits = list.filter((f) => /<SimTeam(?:Link|Logo|Identity)\b[^>]*\bsize=\{\d+\}/.test(strip(readFileSync(f, "utf8")))).map((f) => path.basename(f));
      expect(hits).toEqual([]);
    });
    it(`${label}: a team name is never wrapped in a truncating element`, () => {
      const re = label === "web" ? TRUNCATING_WEB : TRUNCATING_APP;
      const hits = list.flatMap((f) => [...strip(readFileSync(f, "utf8")).matchAll(re)].map((m) => `${path.basename(f)}: ${m[0].replace(/\s+/g, " ").slice(0, 110)}`));
      expect(hits).toEqual([]);
    });
    it(`${label}: a file that prints a team name uses the template (or is in the text-only allowlist)`, () => {
      const hits = list
        .filter((f) => {
          const src = strip(readFileSync(f, "utf8"));
          return NAME_IN_JSX.test(src) && !/<SimTeam(?:Link|Logo|Identity)\b/.test(src) && !(path.basename(f) in TEXT_ONLY);
        })
        .map((f) => path.basename(f));
      expect(hits).toEqual([]);
    });
  }
  it("the recap story itself renders every team through the template", () => {
    for (const f of [path.join(WEB, "SimRecapStory.tsx"), path.join(APP, "SimRecapStory.tsx")]) {
      const src = readFileSync(f, "utf8");
      expect(src).toMatch(/SimTeamIdentity/);
      expect(src).not.toMatch(/TeamAvatar/);
    }
  });
});
