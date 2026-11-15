import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

/** coridian_'s 2026-11-14 picks from docs/audits/ui-pass-5 (D1 pill track, D2 one section title scale, D5 gold = premium + primary only). */
const WEB = path.resolve(__dirname, "..");
const APP = path.resolve(__dirname, "../../../mobile/src");
const read = (root: string, rel: string) => readFileSync(path.join(root, rel), "utf8");

describe("ui pass 5 picks", () => {
  it("D1: the default PillRow is a pill track (radius-segment, no square box, no sliding underline)", () => {
    const src = read(WEB, "components/PillRow.tsx");
    expect(src).toContain('const track = !glass && !slim;');
    expect(src).toContain('borderRadius: "var(--radius-segment)"');
    expect(src).toContain("indicator && !glass && !track");
    expect(read(APP, "components/SegmentedTabBar.tsx")).toContain("borderRadius: radii.pill");
  });

  it("D2: one section title scale; SectionHeading has no size prop and uses --type-app-section-title", () => {
    const src = read(WEB, "components/SectionHeading.tsx");
    expect(src).not.toMatch(/size\??:/);
    expect(src).toContain("--type-app-section-title");
    expect(src).not.toContain('"var(--type-section-title)"');
  });

  it("D5: gold stays off non-premium surfaces (lens name, rank tiles, posture/stance, waiver tones, Draft Capital)", () => {
    const header = read(WEB, "components/Header.tsx");
    expect(header).not.toMatch(/color-premium[^\n]*\n[^\n]*\{leagueName/);
    for (const rel of [
      "components/SnapshotTile.tsx",
      "components/LeagueRankingsContent.tsx",
      "components/DraftCenterContent.tsx",
      "components/GmPlanSections.tsx",
      "components/ui/ModuleTemplates.tsx",
      "lib/waiversPresentation.ts",
      "lib/tradeHubPresentation.ts",
    ]) {
      const src = read(WEB, rel).replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
      expect(src, rel).not.toContain("--color-premium");
    }
    for (const rel of ["components/EvaluationLensHeaderButton.tsx", "screens/DraftCenterScreen.tsx", "components/TradeIdeaCard.tsx", "components/WaiverRecommendationCard.tsx"]) {
      expect(read(APP, rel).replace(/\/\/.*$/gm, ""), rel).not.toContain("colors.premium");
    }
  });

  it("D6: a module's trailing control is one chevron (expand) or the row arrow (navigate): no +/- glyph, no 'Open ->' / 'All ->' header links", () => {
    const web = read(WEB, "components/ui/CompactModule.tsx");
    expect(web).toContain('data-testid="compact-chevron"');
    expect(web).not.toMatch(/"−" : "\+"/);
    expect(read(APP, "components/CompactModule.tsx")).not.toMatch(/'−' : '\+'/);
    expect(read(WEB, "components/DashboardContent.tsx")).not.toMatch(/label2=/);
    expect(read(WEB, "components/GmPlanContent.tsx")).not.toContain('linkAction("View all"');
    expect(read(WEB, "components/ui/ModuleMore.tsx")).toContain("module-more");
    expect(read(APP, "components/ModuleMore.tsx")).toContain("accessibilityRole=\"link\"");
  });
});
