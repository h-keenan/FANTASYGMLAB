import { existsSync, readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Source-scan guard for coridian_'s rule: a player is never shown as a bare name. The avatar is a REQUIRED part of the
 * shared player anatomy (docs/ui-patterns.md, "Player anatomy"): templates take a `player` and draw the avatar
 * themselves (`PlayerAvatarSlot` / `PlayerAvatar`, size from `AVATAR_SIZE`). This fails when a component renders
 * <PlayerName> in a file that never references an avatar, unless the file is on the allowlist below.
 *
 * The allowlist is explicit and may only shrink: every entry is either TEXT (a context where a picture makes no sense,
 * such as a sentence, a tooltip or a chart label) or TODO (a module not yet moved onto the templates, listed in the PR
 * and in docs/ui-patterns.md). An entry that now has an avatar, or whose file is gone, fails the test so it is removed.
 */
const WEB_ALLOW: Record<string, string> = {
  "components/GmOrb.tsx": "TEXT: names inside the assistant's spoken sentences",
  "components/LiveFeedPanel.tsx": "TEXT: names inside a news headline",
  "components/SimToControl.tsx": "TEXT: injury names inside a sentence",
  "components/SimRecapStory.tsx": "TEXT: top-scorer name inside a fact line",
  "components/SimGameTeam.tsx": "TEXT: a native <option> and a sheet title sentence",
};
const APP_ALLOW: Record<string, string> = {
  "components/LiveFeedPanel.tsx": "TEXT: names inside a news headline",
  "components/RoundupPanel.tsx": "TEXT: names inside roundup sentences",
  "components/SimToControl.tsx": "TEXT: injury names inside a sentence",
};

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name !== "node_modules") walk(full, out);
    } else if (/\.tsx$/.test(entry.name) && !/\.test\.tsx$/.test(entry.name)) out.push(full);
  }
  return out;
}

/**
 * The second blind spot closed: a name rendered as a bare JSX expression (`{player.name}`, `{i.player.name}`) with no
 * <PlayerName>. Template literals (aria labels, toasts, sentences built in code) and attribute values are stripped first,
 * so only a name drawn as visible text counts. Exported shape is tested below.
 */
const NAME_ID = "(?:player|p|pl|pick|prospect|asset|mover|retiree|target|[a-z]\\.player)";
const BARE_NAME = new RegExp(`\\{\\s*${NAME_ID}\\??\\.(?:name|player_name|full_name)\\b[^{}]*\\}`);
export function rendersBareName(src: string): boolean {
  const stripped = src.replace(/`[^`]*`/g, "``").replace(/[\w-]+=\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}/g, "");
  return /<PlayerName\b/.test(stripped) || BARE_NAME.test(stripped);
}

const AVATAR = /PlayerAvatar|CompactPlayerCard|PlayerAccordionRow|PlayerListRow|PlayerIdentity(?!Trigger)|PlayerCardKit|PlayerCard/;

function check(root: string, allow: Record<string, string>) {
  const offenders: string[] = [];
  const seen = new Set<string>();
  for (const file of walk(root)) {
    const rel = path.relative(root, file).split(path.sep).join("/");
    const src = readFileSync(file, "utf8");
    if (!rendersBareName(src)) continue;
    const hasAvatar = AVATAR.test(src);
    if (hasAvatar) continue;
    seen.add(rel);
    if (!(rel in allow)) offenders.push(rel);
  }
  const stale = Object.keys(allow).filter((rel) => !seen.has(rel));
  return { offenders, stale };
}

describe("player avatar rule", () => {
  const webRoot = path.resolve(__dirname, "..");
  const appRoot = path.resolve(__dirname, "../../../mobile/src");

  it("web: no component renders a player name without the shared avatar (outside the allowlist)", () => {
    const { offenders, stale } = check(webRoot, WEB_ALLOW);
    expect(offenders, "render the name through PlayerAccordionRow / CompactPlayerCard / PlayerAvatarSlot").toEqual([]);
    expect(stale, "these allowlist entries now have an avatar: remove them").toEqual([]);
  });

  it.skipIf(!existsSync(appRoot))("app: same rule", () => {
    const { offenders, stale } = check(appRoot, APP_ALLOW);
    expect(offenders).toEqual([]);
    expect(stale).toEqual([]);
  });

  it("the scan sees a bare {player.name} but not a sentence, an aria label or an attribute", () => {
    expect(rendersBareName("<span>{player.name}</span>")).toBe(true);
    expect(rendersBareName("<li>{i.player.name} ({i.player.pos})</li>")).toBe(true);
    expect(rendersBareName("<PlayerName name={x} />")).toBe(true);
    expect(rendersBareName("<Button aria-label={`Claim ${player.name}`}>Claim</Button>")).toBe(false);
    expect(rendersBareName("<Row name={player.name} />")).toBe(false);
    expect(rendersBareName("<span>{team.name}</span>")).toBe(false);
  });

  it("the templates draw the avatar themselves", () => {
    for (const root of [path.join(webRoot, "components/ui"), path.join(appRoot, "components")]) {
      if (!existsSync(root)) continue;
      for (const name of ["PlayerAccordionRow", "CompactPlayerCard"]) {
        const file = path.join(root, `${name}.tsx`);
        if (existsSync(file)) expect(readFileSync(file, "utf8"), `${name} must render PlayerAvatarSlot`).toMatch(/PlayerAvatarSlot/);
      }
    }
  });
});
