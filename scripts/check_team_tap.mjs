#!/usr/bin/env node
// Guard for the standing rule "every league team name and avatar opens the shared team sheet" (docs/ui-patterns.md, "Every
// team is tappable"). The one tap target is <TeamNameLink> (web-next/src/components/TeamNameLink.tsx and
// mobile/src/components/TeamNameLink.tsx, logic in the twin lib teamTap.ts). This script fails CI when a screen draws a team
// name as bare text, or a bare <TeamAvatar>, without going through it:
//
//   - A file that renders a team name as JSX text ({x.team_name}, {teamName}, {idea.partner_team_name}) or a raw
//     <TeamAvatar> (and has no `team-tap-exempt: reason` mark on that spot) must be listed in RAW_ALLOWLIST with a reason (a ratchet: new files cannot
//     join the debt, and adopting the component should remove the entry).
//   - A stale entry fails: a listed file with no unmarked bare team name left must be removed.
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

const OWN = "shows the user's own team / league card (a switcher or setup list, not a league-mate), so there is no other team sheet to open; audited in the 2026-11 team tap sweep";
const PROFILE = "the avatar is the signed-in user's own profile picture on the Account/More header, not a league-mate's team, so there is no team sheet to open";
const ROW = "the whole row is already one tap target that opens the team sheet (a name inside it must not nest a second button)";
// path (relative to repo root) -> reason. Only shrinks.
export const RAW_ALLOWLIST = {
  "mobile/src/components/EspnLeagueImport.tsx": OWN,
  "mobile/src/components/LeagueRecapPanel.tsx": ROW,
  "mobile/src/components/LeaguesGlanceSection.tsx": OWN,
  "mobile/src/components/LeagueStandingsModule.tsx": ROW,
  "mobile/src/components/LeagueStandingStrips.tsx": ROW,
  "mobile/src/components/PortfolioStanding.tsx": OWN,
  "mobile/src/components/WeeklyMatchupCard.tsx": ROW,
  "mobile/src/screens/DashboardScreen.tsx": ROW,
  "mobile/src/screens/HomeScreen.tsx": OWN,
  "mobile/src/screens/MoreScreen.tsx": PROFILE,
  "mobile/src/screens/TeamsScreen.tsx": ROW,
  "web-next/src/components/AccountContent.tsx": PROFILE,
  "web-next/src/components/EspnImportForm.tsx": OWN,
  "web-next/src/components/GmPlanSteps.tsx": ROW,
  "web-next/src/components/LeagueRankingsContent.tsx": ROW,
  "web-next/src/components/PortfolioContent.tsx": OWN,
  "web-next/src/components/RecapWeekView.tsx": ROW,
  "web-next/src/components/SleeperImportForm.tsx": OWN,
};

const TEXT_NAME = /[>}]\s*\{\s*[\w.?!]*\b(?:team_name|teamName|partner_team_name)\b\s*(?:\|\|[^}]*|\?\?[^}]*)?\}\s*</g;
const RAW_AVATAR = /<TeamAvatar(?=[\s/>])/g;
// A single bare team name that must stay plain (a picker that selects, a row that is itself the tap target) is marked on the
// same line or up to 3 lines above with `team-tap-exempt: <reason of 12+ characters>`; such a mark exempts only that spot.
const EXEMPT = /team-tap-exempt:\s*\S[^\n]{10,}/;

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    const full = path.join(dir, name);
    const st = statSync(full);
    if (st.isDirectory()) walk(full, out);
    else if (/\.tsx$/.test(name) && !/\.test\.tsx$/.test(name)) out.push(full);
  }
  return out;
}

/** Index just past the `>` that ends the JSX opening tag starting at `start` (handles {} nesting and quotes). */
function tagEnd(src, start) {
  let depth = 0;
  let quote = null;
  for (let i = start; i < src.length; i++) {
    const c = src[i];
    if (quote) {
      if (c === quote && src[i - 1] !== "\\") quote = null;
      continue;
    }
    if (c === '"' || c === "'" || c === "`") { quote = c; continue; }
    if (c === "{") depth++;
    else if (c === "}") depth--;
    else if (c === ">" && depth === 0 && src[i - 1] !== "=") return i + 1;
  }
  return src.length;
}

/** Blank out the children of every <TeamNameLink ...>...</TeamNameLink>: names drawn inside the shared target are the link itself. */
function withoutLinkChildren(src) {
  let out = src;
  const re = /<TeamNameLink(?=[\s/>])/g;
  let m;
  while ((m = re.exec(src))) {
    const end = tagEnd(src, m.index);
    if (src[end - 2] === "/") continue;
    const close = src.indexOf("</TeamNameLink>", end);
    if (close < 0) continue;
    out = out.slice(0, end) + src.slice(end, close).replace(/[^\n]/g, " ") + out.slice(close);
    re.lastIndex = close;
  }
  return out;
}

/** Bare team names / avatars in a source file that carry no exemption mark; `linked` = the file also uses <TeamNameLink>. */
export function scanSource(source) {
  const src = withoutLinkChildren(source);
  const lines = src.split("\n");
  let raw = 0;
  for (const re of [TEXT_NAME, RAW_AVATAR]) {
    re.lastIndex = 0;
    let m;
    while ((m = re.exec(src))) {
      const line = src.slice(0, m.index).split("\n").length - 1;
      const context = lines.slice(Math.max(0, line - 3), line + 1).join("\n");
      if (!EXEMPT.test(context)) raw++;
    }
  }
  return { raw: raw > 0, linked: /<TeamNameLink(?=[\s/>])/.test(source) };
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
      if (raw && !allow[rel]) errors.push(`${rel}: draws a bare team name / <TeamAvatar>; use <TeamNameLink> or add it to RAW_ALLOWLIST in scripts/check_team_tap.mjs with a reason`);
      if (allow[rel] && !raw) errors.push(`${rel}: listed in RAW_ALLOWLIST but no longer draws an unmarked bare team name${linked ? " (it uses <TeamNameLink>)" : ""}; remove it`);
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
