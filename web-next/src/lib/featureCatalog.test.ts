import { existsSync, readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

import { FEATURE_GROUPS, FEATURE_ITEMS, featureHref, featuresPageHref } from "./featureCatalog";
import { useNavDestinations } from "./navDestinations";

const APP_DIR = path.join(process.cwd(), "src", "app");
const MOBILE_CATALOG = path.join(process.cwd(), "..", "mobile", "src", "lib", "featureCatalog.ts");

describe("feature catalog (What FantasyDesk can do)", () => {
  it("has unique ids and only known groups, every group non-empty", () => {
    expect(new Set(FEATURE_ITEMS.map((i) => i.id)).size).toBe(FEATURE_ITEMS.length);
    const groups = new Set(FEATURE_GROUPS.map((g) => g.id));
    for (const item of FEATURE_ITEMS) expect(groups.has(item.group)).toBe(true);
    for (const g of FEATURE_GROUPS) expect(FEATURE_ITEMS.some((i) => i.group === g.id)).toBe(true);
  });

  it.each(FEATURE_ITEMS.map((i) => [i.id, i] as const))("%s opens a route that exists", (_id, item) => {
    const dir = item.leagueScoped ? path.join(APP_DIR, item.segment, "[leagueId]") : path.join(APP_DIR, item.segment);
    expect(existsSync(path.join(dir, "page.tsx")), `${dir}/page.tsx`).toBe(true);
  });

  it("builds league links with the id and name, and falls back to Home without a league", () => {
    const waivers = FEATURE_ITEMS.find((i) => i.id === "waivers")!;
    expect(featureHref(waivers, { id: "L 1", name: "My League" })).toBe("/waivers/L%201?name=My%20League");
    expect(featureHref(waivers, null)).toBe("/");
    const odds = FEATURE_ITEMS.find((i) => i.id === "playoff-odds")!;
    expect(featureHref(odds, { id: "L1", name: "X" })).toBe("/league-rankings/L1?name=X#playoff-odds");
    const news = FEATURE_ITEMS.find((i) => i.id === "news")!;
    expect(featureHref(news, null)).toBe("/news");
    expect(featuresPageHref()).toBe("/features");
  });

  it("uses the same glyph, color and Pro flag as the nav row for the same destination", () => {
    const nav = useNavDestinations("L1", "X");
    const rows = [...nav.coreLeagueDestinations, ...nav.gmToolsDestinations, ...nav.generalDestinations];
    let matched = 0;
    for (const item of FEATURE_ITEMS) {
      const row = rows.find((r) => {
        const first = r.path.split("?")[0].split("#")[0].split("/")[1];
        return first === item.segment && Boolean(r.anchor) === Boolean(item.hash);
      });
      if (!row) continue; // Trade Analyzer / Trade Finder have no nav row on purpose
      matched += 1;
      expect(item.glyph, item.id).toBe(row.glyph);
      expect(item.color, item.id).toBe(row.color);
      expect(Boolean(item.pro), item.id).toBe(Boolean(row.pro));
    }
    expect(matched).toBeGreaterThan(15);
  });

  it("matches the mobile catalog (ids, order, names, Pro flags)", () => {
    const src = readFileSync(MOBILE_CATALOG, "utf8");
    const mobileIds = [...src.matchAll(/\{ id: '([a-z-]+)', group: /g)].map((m) => m[1]);
    expect(mobileIds).toEqual(FEATURE_ITEMS.map((i) => i.id));
    for (const item of FEATURE_ITEMS) {
      const row = src.split("\n").find((l) => l.includes(`id: '${item.id}'`))!;
      expect(row, item.id).toContain(`name: '${item.name}'`);
      expect(row.includes("pro: true"), item.id).toBe(Boolean(item.pro));
    }
  });
});
