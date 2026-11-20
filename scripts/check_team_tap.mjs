#!/usr/bin/env node
// Guard for the standing rule "every league team name and avatar opens the shared team sheet" (docs/ui-patterns.md, "Every
// team is tappable"). The one tap target is <TeamNameLink> (web-next/src/components/TeamNameLink.tsx and
// mobile/src/components/TeamNameLink.tsx, logic in the twin lib teamTap.ts). This script fails CI when a screen draws a team
// name as bare text, or a bare <TeamAvatar>, without going through it:
//
//   - A file that renders a team name as JSX text ({x.team_name}, {teamName}, {idea.partner_team_name}) or a raw
//     <TeamAvatar> and does not use <TeamNameLink> must be listed in RAW_ALLOWLIST with a reason (a ratchet: new files cannot
//     join the debt, and adopting the component should remove the entry).
//   - A stale entry fails: a listed file that now uses <TeamNameLink> or no longer draws a raw team name must be removed.
//   - The component files must keep routing through the shared sheet (ManagerProfileSheet / ManagerProfileModal).
//
// Usage: node scripts/check_team_tap.mjs   (exit 1 on any violation)
import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const TREES = ["web-next/src", "mobile/src"];
const COMPONENT_FILES = {
  "web-next/src/components/TeamNameLink.tsx": /ManagerProfileSheet/,
  "mobile/src/components/TeamNameLink.tsx": /ManagerProfileModal/,
};
// Files that ARE the sheet / avatar / share-image primitives, or design-system demos.
const SKIP = /\/(TeamNameLink|TeamAvatar|ManagerProfileSheet|ManagerProfileModal)\.tsx$|\/shareCard\/|ShareCard\.tsx$|\/design\//;

const MATCHUP = "the Matchup page is being reworked in PR #2230; adopt <TeamNameLink> in a follow-up after it merges";
const OWN = "shows the user's own team / league card (a switcher or setup list, not a league-mate), so there is no other team sheet to open; audited in the 2026-11 team tap sweep";
const ROW = "the whole row is already one tap target that opens the team sheet (a name inside it must not nest a second button)";
const PENDING = "not yet moved to TeamNameLink (ratchet: adopt <TeamNameLink> here and delete this entry)";
// path (relative to repo root) -> reason. Only shrinks.
export const RAW_ALLOWLIST = {
  "mobile/src/components/EspnLeagueImport.tsx": OWN,
  "mobile/src/components/LeaguePulseCard.tsx": PENDING,
  "mobile/src/components/LeagueRecapPanel.tsx": ROW,
  "mobile/src/components/LeaguesGlanceSection.tsx": OWN,
  "mobile/src/components/LeagueStandingsModule.tsx": ROW,
  "mobile/src/components/LeagueStandingStrips.tsx": ROW,
  "mobile/src/components/LiveDraftRoom.tsx": PENDING,
  "mobile/src/components/MatchupLineup.tsx": MATCHUP,
  "mobile/src/components/MultiTeamTradePanel.tsx": PENDING,
  "mobile/src/components/PortfolioStanding.tsx": OWN,
  "mobile/src/components/VetoCalculator.tsx": OWN,
  "mobile/src/components/WeeklyMatchupCard.tsx": MATCHUP,
  "mobile/src/screens/CommissionerScreen.tsx": OWN,
  "mobile/src/screens/DashboardScreen.tsx": OWN,
  "mobile/src/screens/DraftCenterScreen.tsx": PENDING,
  "mobile/src/screens/GamesScreen.tsx": PENDING,
  "mobile/src/screens/HomeScreen.tsx": OWN,
  "mobile/src/screens/MatchupScreen.tsx": MATCHUP,
  "mobile/src/screens/PlayoffOddsPanel.tsx": PENDING,
  "mobile/src/screens/TeamsScreen.tsx": ROW,
  "mobile/src/screens/TradeAnalyzerScreen.tsx": PENDING,
  "web-next/src/components/CommissionerContent.tsx": OWN,
  "web-next/src/components/DraftCenterContent.tsx": PENDING,
  "web-next/src/components/EspnImportForm.tsx": OWN,
  "web-next/src/components/GamesContent.tsx": PENDING,
  "web-next/src/components/GmPlanSteps.tsx": OWN,
  "web-next/src/components/LeaguePulseCard.tsx": PENDING,
  "web-next/src/components/LeagueRankingsContent.tsx": ROW,
  "web-next/src/components/MatchupContent.tsx": MATCHUP,
  "web-next/src/components/MatchupLineup.tsx": MATCHUP,
  "web-next/src/components/PortfolioContent.tsx": OWN,
  "web-next/src/components/RecapWeekView.tsx": ROW,
  "web-next/src/components/SleeperImportForm.tsx": OWN,
  "web-next/src/components/VetoCalculator.tsx": OWN,
};

const TEXT_NAME = /[>}]\s*\{\s*[\w.?!]*\b(?:team_name|teamName|partner_team_name)\b\s*(?:\|\|[^}]*|\?\?[^}]*)?\}\s*</;
const RAW_AVATAR = /<TeamAvatar(?=[\s/>])/;

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    const full = path.join(dir, name);
    const st = statSync(full);
    if (st.isDirectory()) walk(full, out);
    else if (/\.tsx$/.test(name) && !/\.test\.tsx$/.test(name)) out.push(full);
  }
  return out;
}

/** What a source file does with team identity: raw = draws a bare name/avatar, linked = uses <TeamNameLink>. */
export function scanSource(src) {
  return { raw: TEXT_NAME.test(src) || RAW_AVATAR.test(src), linked: /<TeamNameLink(?=[\s/>])/.test(src) };
}

export function run(root = ROOT, allow = RAW_ALLOWLIST) {
  const errors = [];
  for (const [f, needle] of Object.entries(COMPONENT_FILES)) {
    let src = "";
    try {
      src = readFileSync(path.join(root, f), "utf8");
    } catch {
      errors.push(`${f}: the shared TeamNameLink is missing`);
      continue;
    }
    if (!needle.test(src)) errors.push(`${f}: must open the shared team sheet (${needle.source}); do not build a second sheet`);
    if (!/aria-label|accessibilityLabel/.test(src)) errors.push(`${f}: the tap target needs an accessible label`);
  }
  const seen = new Set();
  for (const tree of TREES) {
    for (const file of walk(path.join(root, tree))) {
      const rel = path.relative(root, file);
      if (SKIP.test(rel)) continue;
      const { raw, linked } = scanSource(readFileSync(file, "utf8"));
      seen.add(rel);
      if (raw && !linked && !allow[rel]) errors.push(`${rel}: draws a bare team name / <TeamAvatar>; use <TeamNameLink> or add it to RAW_ALLOWLIST in scripts/check_team_tap.mjs with a reason`);
      if (allow[rel] && (!raw || linked)) errors.push(`${rel}: listed in RAW_ALLOWLIST but ${linked ? "now uses <TeamNameLink>" : "no longer draws a bare team name"}; remove it`);
    }
  }
  for (const rel of Object.keys(allow)) {
    if (!seen.has(rel)) errors.push(`${rel}: listed in RAW_ALLOWLIST but the file no longer exists; remove it`);
  }
  return errors;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const errors = run();
  if (errors.length) {
    console.error(`team tap check failed (${errors.length}):\n` + errors.map((e) => `  - ${e}`).join("\n"));
    process.exit(1);
  }
  console.log("team tap check passed");
}
