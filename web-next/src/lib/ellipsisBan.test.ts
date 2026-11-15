import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Source-scan ban (docs/ui-patterns.md, "Never ellipsize"): the line under a player name (TEAM / Age / Bye / PROJ), a team
 * name and a stat line are never cut with an ellipsis, a line-clamp or numberOfLines. They go through PlayerMetaLine (the
 * priority ladder in lib/playerMetaFit.ts) or wrap. Person names have their own scan (playerNameTruncation.test.ts).
 * Two checks:
 *   - STRICT files (the shared row / card / sub-line primitives, both platforms) hold no truncation at all, except the
 *     reasoned ALLOW entries (a news headline clamp);
 *   - app: no `numberOfLines` Text whose style is a sub-line / team / stat style (team, context, subline, meta ...), anywhere.
 * The page-level twin is scripts/sim_layout_playwright/guard_checks.mjs (asserts no ellipsis is actually cutting text).
 */
const WEB = path.resolve(__dirname, "..");
const APP = path.resolve(__dirname, "../../../mobile/src");

const STRICT_WEB = [
  "components/ui/PlayerAccordionRow.tsx",
  "components/ui/PlayerMetaLine.tsx",
  "components/ui/CompactPlayerCard.tsx",
  "components/PlayerCardKit.tsx",
  "components/PlayerRow.tsx",
  "components/PlayerListRow.tsx",
  "components/MatchupLineup.tsx",
  "components/SimMoveStrip.tsx",
  "components/SimDraftGrid.tsx",
  "components/SuggestedDrop.tsx",
  "components/LiveDraftTradeEvaluator.tsx",
];
const STRICT_APP = ["components/PlayerAccordionRow.tsx", "components/PlayerMetaLine.tsx", "components/MatchupLineup.tsx", "components/CompactPlayerModule.tsx", "components/DraftPickAssetRow.tsx"];
/** file -> substrings of the allowed lines (each with its reason). */
const ALLOW: Record<string, string[]> = {
  "components/PlayerAccordionRow.tsx": ["numberOfLines={2} testID=\"row-headline\""],
  // News headline: a sentence, not a name or stat; two lines then the row opens.
  "components/ui/PlayerAccordionRow.tsx": ["WebkitLineClamp: 2", "numberOfLines={2} testID=\"row-headline\""],
  // Trailing figure (one value, always short): shrinks the text, never cuts it.
  "components/CompactPlayerModule.tsx": ["styles.trailingValue", "styles.trailingCaption"],
  "components/DraftPickAssetRow.tsx": ["styles.label", "styles.trailingValue", "styles.trailingCaption"],
};
/** Fixed-size share canvases (an exported image, not a scrolling screen): their sub-lines clamp so the card keeps its shape. */
const SHARE_CANVAS = /ShareCard\.tsx$/;
const WEB_BAN = /\btruncate\b|text-ellipsis|line-clamp|textOverflow|WebkitLineClamp/;
const APP_BAN = /numberOfLines|ellipsizeMode|adjustsFontSizeToFit/;
const SUBLINE_STYLE = /style=\{(?:\[\s*)?styles\.(team|teamName|context|subline|miniSub|meta|slotText|subtitle|sublabel)\b/;

const strip = (src: string) => src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
function walk(dir: string, out: string[] = []): string[] {
  for (const e of readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) { if (e.name !== "node_modules") walk(full, out); } else if (/\.tsx$/.test(e.name) && !/\.test\./.test(e.name)) out.push(full);
  }
  return out;
}

describe("sub-lines under names, team names and stats are never ellipsized", () => {
  it("web: the shared row / card primitives hold no truncation", () => {
    const bad = STRICT_WEB.flatMap((f) => strip(readFileSync(path.join(WEB, f), "utf8")).split("\n").map((line, i) => (WEB_BAN.test(line) && !(ALLOW[f] ?? []).some((a) => line.includes(a)) ? `${f}:${i + 1}: ${line.trim().slice(0, 100)}` : "")).filter(Boolean));
    expect(bad).toEqual([]);
  });
  it("app: the shared row / card primitives hold no truncation", () => {
    const bad = STRICT_APP.flatMap((f) => strip(readFileSync(path.join(APP, f), "utf8")).split("\n").map((line, i) => (APP_BAN.test(line) && !(ALLOW[f] ?? []).some((a) => line.includes(a)) ? `${f}:${i + 1}: ${line.trim().slice(0, 100)}` : "")).filter(Boolean));
    expect(bad).toEqual([]);
  });
  it("app: no numberOfLines on a sub-line / team / stat style anywhere", () => {
    const bad: string[] = [];
    for (const file of walk(APP)) {
      if (SHARE_CANVAS.test(file)) continue;
      const lines = strip(readFileSync(file, "utf8")).split("\n");
      lines.forEach((line, i) => {
        if (!/numberOfLines=/.test(line) && !/<(?:AppText|Text)\b/.test(line)) return;
        const el = lines.slice(i, i + 4).join(" ");
        const open = el.slice(0, el.indexOf(">") === -1 ? undefined : el.indexOf(">") + 1);
        if (/<(?:AppText|Text)\b/.test(line) && /numberOfLines=/.test(open) && SUBLINE_STYLE.test(open)) bad.push(`${path.relative(APP, file)}:${i + 1}: ${line.trim().slice(0, 100)}`);
      });
    }
    expect(bad).toEqual([]);
  });
  it("the detectors catch a truncated sub-line", () => {
    expect(WEB_BAN.test('<span className="min-w-0 truncate">')).toBe(true);
    expect(APP_BAN.test("<AppText numberOfLines={1}>")).toBe(true);
    expect(SUBLINE_STYLE.test("<AppText style={styles.team} numberOfLines={1}>")).toBe(true);
  });
});
