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
  "components/seo/PublicTradeAnalyzer.tsx": "TODO: public marketing analyzer, move onto TradeCompactCard",
  "components/ManagerProfileSheet.tsx": "TODO: manager trade history lines",
  "components/OpponentProfileCard.tsx": "TODO: opponent profile target lines",
  "components/SampleLeagueContent.tsx": "TODO: sample league roster rows",
  "components/SimDraftGrid.tsx": "TODO: draft grid cells (name only in a tight grid)",
  "components/SimTeamCard.tsx": "TODO: sim team card key players",
  "components/SimTeamHistory.tsx": "TODO: sim history award lines",
};
const APP_ALLOW: Record<string, string> = {
  "components/LiveFeedPanel.tsx": "TEXT: names inside a news headline",
  "components/RoundupPanel.tsx": "TEXT: names inside roundup sentences",
  "components/ManagerProfileModal.tsx": "TODO: manager trade history lines",
  "components/OpponentProfileCard.tsx": "TODO: opponent profile target lines",
  "components/SimDraftGrid.tsx": "TODO: draft grid cells",
  "components/SimTeamCard.tsx": "TODO: sim team card key players",
  "components/SimTeamHistory.tsx": "TODO: sim history award lines",
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

const AVATAR = /PlayerAvatar|CompactPlayerCard|PlayerAccordionRow|PlayerListRow|PlayerIdentity|PlayerCardKit|PlayerCard/;

function check(root: string, allow: Record<string, string>) {
  const offenders: string[] = [];
  const seen = new Set<string>();
  for (const file of walk(root)) {
    const rel = path.relative(root, file).split(path.sep).join("/");
    const src = readFileSync(file, "utf8");
    if (!/<PlayerName\b/.test(src)) continue;
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
