import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Lint-style guard for the owner's rule: a player name must never be raw
 * ellipsized. Anywhere a name could be cut off it goes through <PlayerName/>
 * (first initial + whole surname, ellipsis only as the last resort). This
 * flags a truncating element (web `truncate`, mobile `numberOfLines={1}`)
 * whose child is a bare player-name expression.
 */
const NAME_EXPR = String.raw`\{\s*(?:[\w.?]*\b(?:player|card|asset|p|playerA|playerB|prospect|target|standout)\??\.name|[\w.?]*player_name|[\w.?]*\.playerName)\s*\}`;
const WEB = new RegExp(String.raw`<(?:span|div|p)\b[^>]*\b(?:truncate|text-ellipsis)\b[^>]*>\s*${NAME_EXPR}`, "g");
const NATIVE = new RegExp(String.raw`<AppText\b[^>]*numberOfLines=\{1\}[^>]*>\s*${NAME_EXPR}`, "g");

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === "node_modules") continue;
      walk(full, out);
    } else if (/\.tsx$/.test(entry.name) && !/\.test\.tsx$/.test(entry.name)) out.push(full);
  }
  return out;
}

function offenders(root: string, re: RegExp): string[] {
  const hits: string[] = [];
  for (const file of walk(root)) {
    const src = readFileSync(file, "utf8");
    for (const match of src.matchAll(re)) hits.push(`${path.relative(root, file)}: ${match[0].replace(/\s+/g, " ").slice(0, 120)}`);
  }
  return hits;
}

describe("player names are never raw-truncated", () => {
  it("web components render names through PlayerName", () => {
    expect(offenders(path.resolve(__dirname, ".."), WEB)).toEqual([]);
  });

  it("mobile components render names through PlayerName", () => {
    expect(offenders(path.resolve(__dirname, "../../../mobile/src"), NATIVE)).toEqual([]);
  });

  it("the detector catches a raw truncated name", () => {
    expect([..."<span className=\"truncate\">{player.name}</span>".matchAll(WEB)]).toHaveLength(1);
    expect([..."<AppText style={s} numberOfLines={1}>\n {card.name}\n</AppText>".matchAll(NATIVE)]).toHaveLength(1);
    expect([..."<PlayerName name={player.name} />".matchAll(WEB)]).toHaveLength(0);
  });
});
