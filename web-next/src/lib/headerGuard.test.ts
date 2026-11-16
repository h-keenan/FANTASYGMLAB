import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

import { headerShowsTitle, repeatsLabel, TAB_PAGE_SEGMENTS } from "./appHeader";
import { PAGE_TAB_FAMILIES } from "./pageFamilies";
import { shellTabs } from "./shellNav";

/** Header rules (docs/audits/2026-11-header-rewrite.md, coridian_ picked V2): a label appears once; league names never ellipsize; one header system. */
const WEB = path.resolve(__dirname, "..");
const APP = path.resolve(__dirname, "../../../mobile/src");
const read = (root: string, rel: string) => readFileSync(path.join(root, rel), "utf8");

describe("header guard", () => {
  it("no tab page shows a header title: every pill and family-tab page is a root header", () => {
    const pillSegments = new Set<string>();
    for (const family of PAGE_TAB_FAMILIES) for (const tab of family.tabs) pillSegments.add(tab.segment);
    for (const seg of pillSegments) expect(headerShowsTitle(`/${seg}/L1`), seg).toBe(false);
    for (const seg of ["dashboard", "my-team", "trade-hub", "league-rankings"]) expect(TAB_PAGE_SEGMENTS).toContain(seg);
  });

  it("the shell tab labels never equal a visible header title", () => {
    for (const tab of shellTabs({ leagueId: "L1", leagueName: "L" })) expect(repeatsLabel(headerShowsTitle("/gm-plan/L1") ? "GM Plan" : "", [tab.label])).toBe(false);
  });

  it("ShellHeader is the one phone header: it uses the shared rules, the switcher sheet and no ellipsis on league names", () => {
    const shell = read(WEB, "components/ShellHeader.tsx");
    expect(shell).toContain("headerShowsTitle");
    expect(shell).toContain("LeagueSwitcherSheet");
    expect(shell).not.toContain("LeagueLensPicker");
    expect(shell).not.toMatch(/shell-header-league[^\n]*truncate/);
    const sheet = read(WEB, "components/LeagueSwitcherSheet.tsx");
    expect(sheet).toContain("break-words");
    // The league rows are buttons that router.push: they must mark the navigation or closing the sheet history.go(-1)s over it.
    expect(sheet).toMatch(/markOverlayNavigating\(\);\s*onClose\(\);/);
    expect(sheet).not.toMatch(/truncate|line-clamp|text-ellipsis/);
  });

  it("app switcher: names wrap (no numberOfLines on the league name), crest, search from 6", () => {
    const app = read(APP, "components/LeagueSwitcherHeaderButton.tsx");
    expect(app).not.toMatch(/numberOfLines=\{1\}>\s*\{row\.league_name/);
    expect(app).toContain("LeagueCrest");
    expect(app).toContain("SWITCHER_SEARCH_FROM");
  });

  it("the status-header kickers do not repeat a page label (Today / Team)", () => {
    const src = read(WEB, "lib/statusHeader.ts");
    expect(src).not.toContain("`TODAY · WEEK");
    expect(src).not.toContain('kicker: "TEAM"');
  });

  it("the Sim game header is one 52px row plus a folding ribbon (web and app), never the old two-row 97px block", () => {
    const web = read(WEB, "components/SimGameHeader.tsx");
    expect(web).toContain("sim-game-header-row");
    expect(web).toContain("ribbonCollapsed");
    const css = read(WEB, "app/globals.css");
    expect(css).toMatch(/\.sim-game-header \{[^}]*flex-direction: column/);
    expect(css).not.toMatch(/\.sim-game-header \{[^}]*flex-wrap: wrap/);
    const app = read(APP, "components/SimGameHeader.tsx");
    expect(app).toContain("ribbon");
    expect(app).not.toMatch(/width: '100%'/);
  });
});
