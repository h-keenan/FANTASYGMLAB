import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Source-scan guard for the owner's rule (said five times): a person name is NEVER ellipsized. Wherever it could be cut
 * off it goes through <PlayerName/> (web components/PlayerName.tsx, app components/PlayerName.tsx), which walks the one
 * ladder in lib/playerNameFit.ts: full name -> "J. Surname" (whole surname, suffix kept) -> a font step smaller -> two
 * steps -> wrapped. This fails when
 *   - PlayerName itself (either platform) uses an ellipsis / truncate / line-clamp,
 *   - a <PlayerName> is given a truncating class,
 *   - a truncating element (web `truncate` / `text-ellipsis` / `line-clamp`, app `numberOfLines`) wraps a bare person-name
 *     expression (`.name`, `player_name`, `playerName`),
 *   - a surname is hand-cut with `.split(" ").slice(-1)[0]` (use playerSurname from lib/playerNameDisplay.ts).
 * Team, league and manager names are not person names; they are the explicit allowlist below.
 */
const NAME_EXPR = String.raw`\{[^{}]*?(?:player_name|playerName|\.name)\b[^{}]*\}`;
const WEB = new RegExp(String.raw`<(?:span|div|p|a|button|h\d)\b[^>]*\b(?:truncate|text-ellipsis|line-clamp-\d)\b[^>]*>\s*${NAME_EXPR}`, "g");
const NATIVE = new RegExp(String.raw`<(?:AppText|Text)\b[^>]*numberOfLines=\{\d\}[^>]*>\s*${NAME_EXPR}`, "g");
const HAND_CUT = /\.split\((?:" "|' '|\/\\s\+\/)\)\.slice\(-1\)\[0\]/;

// Team / manager names (not people): file basename + the expression it renders.
const TEAM_NAMES = [
  ["SimDraftGrid.tsx", 't.is_you ? "You" : t.name'],
  ["SimDraftGrid.tsx", "t.is_you ? 'You' : t.name"],
  ["SimGameRecap.tsx", "row.name"],
  ["SimGameTrades.tsx", "item.from.name"],
  ["SimTeamCard.tsx", "team.name"],
  ["SimGameParts.tsx", "name"],
  ["MultiTeamTradeShareCard.tsx", "team.name"],
  ["HomeScreen.tsx", "item.name || item.league_id"],
  ["SimRecapStory.tsx", "name"],
  // Draft-pick rows (not a player): the pick label.
  ["RecapTradeDetailModal.tsx", "asset.label || asset.name"],
] as const;

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === "node_modules") continue;
      walk(full, out);
    } else if (/\.tsx?$/.test(entry.name) && !/\.test\.tsx?$/.test(entry.name)) out.push(full);
  }
  return out;
}

function offenders(root: string, re: RegExp, only = /\.tsx$/): string[] {
  const hits: string[] = [];
  for (const file of walk(root).filter((f) => only.test(f))) {
    const src = readFileSync(file, "utf8");
    for (const match of src.matchAll(re)) {
      const flat = match[0].replace(/\s+/g, " ");
      const base = path.basename(file);
      if (TEAM_NAMES.some(([f, expr]) => f === base && flat.includes(`{${expr}`))) continue;
      hits.push(`${path.relative(root, file)}: ${flat.slice(0, 130)}`);
    }
  }
  return hits;
}

const WEB_ROOT = path.resolve(__dirname, "..");
const APP_ROOT = path.resolve(__dirname, "../../../mobile/src");

describe("player names are never ellipsized", () => {
  it("web: no truncating element wraps a bare person name", () => {
    expect(offenders(WEB_ROOT, WEB)).toEqual([]);
  });
  it("app: no numberOfLines Text wraps a bare person name", () => {
    expect(offenders(APP_ROOT, NATIVE)).toEqual([]);
  });
  it("PlayerName (web) never truncates; PlayerName (app) never ellipsizes", () => {
    const web = readFileSync(path.join(WEB_ROOT, "components/PlayerName.tsx"), "utf8").replace(/\/\*[\s\S]*?\*\//g, "").replace(/\{\/\*[\s\S]*?\*\/\}/g, "");
    expect(web).not.toMatch(/\btruncate\b|text-ellipsis|line-clamp|textOverflow/);
    const app = readFileSync(path.join(APP_ROOT, "components/PlayerName.tsx"), "utf8").replace(/\/\*[\s\S]*?\*\//g, "").replace(/\/\/.*$/gm, "");
    expect(app).not.toMatch(/ellipsizeMode="(?!clip)|ellipsizeMode='(?!clip)|adjustsFontSizeToFit/);
  });
  it("nobody passes a truncating class to <PlayerName>", () => {
    expect(offenders(WEB_ROOT, /<PlayerName\b[^>]*\b(?:truncate|text-ellipsis|line-clamp-\d)\b[^>]*>/g)).toEqual([]);
  });
  it("nobody hand-cuts a surname (use playerSurname)", () => {
    const hits: string[] = [];
    for (const root of [WEB_ROOT, APP_ROOT]) {
      for (const file of walk(root)) {
        if (/playerNameDisplay\.ts$/.test(file)) continue;
        readFileSync(file, "utf8").split("\n").forEach((line, i) => {
          if (HAND_CUT.test(line)) hits.push(`${path.relative(root, file)}:${i + 1}`);
        });
      }
    }
    expect(hits).toEqual([]);
  });
  it("the detectors catch a raw truncated name and let PlayerName through", () => {
    expect([..."<span className=\"truncate\">{player.name}</span>".matchAll(WEB)]).toHaveLength(1);
    expect([..."<AppText style={s} numberOfLines={1}>\n {card.name}\n</AppText>".matchAll(NATIVE)]).toHaveLength(1);
    expect([..."<PlayerName name={player.name} />".matchAll(WEB)]).toHaveLength(0);
    expect(HAND_CUT.test('p.name.split(" ").slice(-1)[0]')).toBe(true);
  });
});
