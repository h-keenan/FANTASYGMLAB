import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

/** UI pass 5 D3 (page "?" lives in the header only) and D9 (Trade Finder roster row = the approved player row). coridian_, 2026-11-14. */
const WEB = path.resolve(__dirname, "..");
const APP = path.resolve(__dirname, "../../../mobile/src");
const read = (root: string, rel: string) => readFileSync(path.join(root, rel), "utf8");

describe("ui pass 5 (D3, D9)", () => {
  it("D3: no labelled inline page '?' rows; the four pages hand their lines to PageTitle info", () => {
    for (const rel of ["components/MyTeamContent.tsx", "components/MatchupContent.tsx", "components/LeagueRankingsContent.tsx", "components/WaiversContent.tsx"]) {
      const src = read(WEB, rel);
      expect(src, rel).not.toMatch(/<BeginnerHelp[^>]*label="(My Team and value tiers|this matchup page|playoff odds|waiver value|waiver confidence)"/);
      expect(src, rel).toMatch(/<PageTitle page="[^"]+" leagueName=\{leagueName\} info=\{/);
    }
    expect(read(WEB, "components/PageHelpLines.tsx")).toContain("copy.showsHelp");
  });

  it("D9: the Trade Finder roster row is the approved player row in selection mode (web and app)", () => {
    const web = read(WEB, "components/TradeFinderContent.tsx");
    expect(web).toContain("<PlayerAccordionRow");
    expect(web).not.toContain("<PlayerIdentity");
    expect(read(WEB, "components/ui/PlayerAccordionRow.tsx")).toContain("aria-pressed={selected}");
    const app = read(APP, "screens/TradeFinderScreen.tsx");
    expect(app).toContain("<PlayerAccordionRow");
    expect(app).toContain("testID=\"trade-finder-roster-row\"");
  });
});
