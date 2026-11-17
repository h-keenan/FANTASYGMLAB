#!/usr/bin/env node
// Guard for the standing rule "every player and pick shown anywhere opens the quick view" (docs/ui-patterns.md, "Every
// player and pick is tappable"). The shared templates (CompactPlayerCard, PlayerAccordionRow, TradeAssetCard,
// PlayerAvatarSlot, SimPlayerChip) are tappable by default, so a forgotten tap handler cannot exist; this script makes
// the remaining ways to break the rule fail CI:
//
//   1. A template tag marked `nonInteractive` must carry a real reason (a quoted sentence of 12+ characters, or an
//      identifier that the same file defines as one). No bare flag, no empty string.
//   2. The template files must still route through PlayerTap / PickTap (nobody can quietly delete the default).
//   3. A template that is tappable by default must not sit inside a <button>, <a>/<Link>, <Pressable> or
//      <PressableScale> without `nonInteractive` (that would nest one tap target in another).
//   4. Raw identity primitives (<PlayerAvatar>, <PlayerName>) outside the templates are a ratchet: only the files listed in
//      RAW_ALLOWLIST (each with a reason: the file wires its own tap, or it is a screen that may not be tappable) may use
//      them. A new file that draws a bare avatar or name must either use a template or be added here with a reason.
//   5. Avatars always carry identity (the photo fallback chain, lib/avatarFallback.ts): every <PlayerAvatar> must pass
//      `name` (and ideally `position`/`team`) and every <TeamAvatar> must pass `name`, so a missing photo becomes a monogram and
//      never an empty circle. Files marked "exempt:" in RAW_ALLOWLIST (identity hidden on purpose) are skipped.
//
// Usage: node scripts/check_player_tap.mjs   (exit 1 on any violation)
import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const TREES = ["web-next/src", "mobile/src"];
const TEMPLATES = ["CompactPlayerCard", "PlayerAvatarSlot", "TradeAssetCard", "SimPlayerChip", "PlayerAccordionRow"];
const CONTAINERS = ["button", "a", "Link", "Pressable", "PressableScale", "TouchableOpacity"];
const TEMPLATE_FILES = [
  "web-next/src/components/ui/CompactPlayerCard.tsx",
  "web-next/src/components/ui/PlayerAvatarSlot.tsx",
  "web-next/src/components/ui/TradeCompactCard.tsx",
  "web-next/src/components/ui/PlayerAccordionRow.tsx",
  "mobile/src/components/CompactPlayerCard.tsx",
  "mobile/src/components/PlayerAvatarSlot.tsx",
  "mobile/src/components/TradeCompactCard.tsx",
  "mobile/src/components/PlayerAccordionRow.tsx",
];
// Files allowed to render a raw <PlayerAvatar>/<PlayerName>: path (relative to repo root) -> reason.
export const RAW_ALLOWLIST = {
  "web-next/src/components/NewsDigest.tsx": "exempt: the player chips are filter toggles that select a player to filter by (picker rule); the story rows use PlayerAccordionRow, tappable by default",
  "mobile/src/components/NewsDigest.tsx": "exempt: the player chips are filter toggles that select a player to filter by (picker rule); the story rows use PlayerAccordionRow, tappable by default",
  "mobile/src/components/CollegeScoutingPanel.tsx": "draws its own identity markup and wires its own tap (PlayerTap, PlayerIdentityTrigger or the PQV opener), audited in the 2026-11-14 tap sweep",
  "mobile/src/components/CompactPlayerModule.tsx": "draws its own identity markup and wires its own tap (PlayerTap, PlayerIdentityTrigger or the PQV opener), audited in the 2026-11-14 tap sweep",
  "mobile/src/components/CompareShareCard.tsx": "exempt: a rendered share-card image, not interactive UI",
  "mobile/src/components/GuessThePlayerNameMatchPrompt.tsx": "exempt: the guessing game hides the player identity until answered",
  "mobile/src/components/GuessThePlayerPrompt.tsx": "exempt: the guessing game hides the player identity until answered",
  "mobile/src/components/LiveFeedPanel.tsx": "draws its own identity markup and wires its own tap (PlayerTap, PlayerIdentityTrigger or the PQV opener), audited in the 2026-11-14 tap sweep",
  "mobile/src/components/MatchupLineup.tsx": "draws its own identity markup and wires its own tap (PlayerTap, PlayerIdentityTrigger or the PQV opener), audited in the 2026-11-14 tap sweep",
  "mobile/src/components/MatchupModule.tsx": "draws its own identity markup and wires its own tap (PlayerTap, PlayerIdentityTrigger or the PQV opener), audited in the 2026-11-14 tap sweep",
  "mobile/src/components/PercentileExplorerSheet.tsx": "draws its own identity markup and wires its own tap (PlayerTap, PlayerIdentityTrigger or the PQV opener), audited in the 2026-11-14 tap sweep",
  "mobile/src/components/PlayerCard.tsx": "draws its own identity markup and wires its own tap (PlayerTap, PlayerIdentityTrigger or the PQV opener), audited in the 2026-11-14 tap sweep",
  "mobile/src/components/PlayerCardKit.tsx": "draws its own identity markup and wires its own tap (PlayerTap, PlayerIdentityTrigger or the PQV opener), audited in the 2026-11-14 tap sweep",
  "mobile/src/components/PlayerHero.tsx": "exempt: the player's own profile hero (already on that player)",
  "mobile/src/components/PlayerIdentityRow.tsx": "draws its own identity markup and wires its own tap (PlayerTap, PlayerIdentityTrigger or the PQV opener), audited in the 2026-11-14 tap sweep",
  "mobile/src/components/PlayerListRow.tsx": "draws its own identity markup and wires its own tap (PlayerTap, PlayerIdentityTrigger or the PQV opener), audited in the 2026-11-14 tap sweep",
  "mobile/src/components/PlayerShareCard.tsx": "exempt: a rendered share-card image, not interactive UI",
  "mobile/src/components/PortfolioShareCard.tsx": "exempt: a rendered share-card image, not interactive UI",
  "mobile/src/components/RoundupPanel.tsx": "draws its own identity markup and wires its own tap (PlayerTap, PlayerIdentityTrigger or the PQV opener), audited in the 2026-11-14 tap sweep",
  "mobile/src/components/SimDraftBar.tsx": "draws its own identity markup and wires its own tap (PlayerTap, PlayerIdentityTrigger or the PQV opener), audited in the 2026-11-14 tap sweep",
  "mobile/src/components/SimDraftOverview.tsx": "draws its own identity markup (the fixed Just-drafted card layout); the whole card button wires the tap (onOpenPlayer opens the player) and the avatar inside is nonInteractive",
  "mobile/src/components/SimDraftGrid.tsx": "draws its own identity markup and wires its own tap (PlayerTap, PlayerIdentityTrigger or the PQV opener), audited in the 2026-11-14 tap sweep",
  "mobile/src/components/SimDraftHero.tsx": "draws its own identity markup and wires its own tap (PlayerTap, PlayerIdentityTrigger or the PQV opener), audited in the 2026-11-14 tap sweep",
  "mobile/src/components/SimGameParts.tsx": "draws its own identity markup and wires its own tap (PlayerTap, PlayerIdentityTrigger or the PQV opener), audited in the 2026-11-14 tap sweep",
  "mobile/src/components/SuggestedDrop.tsx": "draws its own identity markup and wires its own tap (PlayerTap, PlayerIdentityTrigger or the PQV opener), audited in the 2026-11-14 tap sweep",
  "mobile/src/components/TradePickerSheet.tsx": "draws its own identity markup and wires its own tap (PlayerTap, PlayerIdentityTrigger or the PQV opener), audited in the 2026-11-14 tap sweep",
  "mobile/src/components/TradeShareCard.tsx": "exempt: a rendered share-card image, not interactive UI",
  "mobile/src/components/WaiverSuggestionsStrip.tsx": "draws its own identity markup and wires its own tap (PlayerTap, PlayerIdentityTrigger or the PQV opener), audited in the 2026-11-14 tap sweep",
  "mobile/src/screens/PlayerCompareScreen.tsx": "draws its own identity markup and wires its own tap (PlayerTap, PlayerIdentityTrigger or the PQV opener), audited in the 2026-11-14 tap sweep",
  "mobile/src/screens/WaiversScreen.tsx": "draws its own identity markup and wires its own tap (PlayerTap, PlayerIdentityTrigger or the PQV opener), audited in the 2026-11-14 tap sweep",
  "web-next/src/components/AlertsContent.tsx": "draws its own identity markup and wires its own tap (PlayerTap, PlayerIdentityTrigger or the PQV opener), audited in the 2026-11-14 tap sweep",
  "web-next/src/components/BriefingItemPlayers.tsx": "draws its own identity markup and wires its own tap (PlayerTap, PlayerIdentityTrigger or the PQV opener), audited in the 2026-11-14 tap sweep",
  "web-next/src/components/NavSheet.tsx": "draws its own identity markup and wires its own tap (PlayerTap, PlayerIdentityTrigger or the PQV opener), audited in the 2026-11-14 tap sweep",
  "web-next/src/components/GuessThePlayerCard.tsx": "exempt: the guessing game hides the player identity until answered",
  "web-next/src/components/GuessThePlayerNameMatchCard.tsx": "exempt: the guessing game hides the player identity until answered",
  "web-next/src/components/LeagueHistoryTab.tsx": "draws its own identity markup and wires its own tap (PlayerTap, PlayerIdentityTrigger or the PQV opener), audited in the 2026-11-14 tap sweep",
  "web-next/src/components/LiveFeedPanel.tsx": "draws its own identity markup and wires its own tap (PlayerTap, PlayerIdentityTrigger or the PQV opener), audited in the 2026-11-14 tap sweep",
  "web-next/src/components/MatchupLineup.tsx": "draws its own identity markup and wires its own tap (PlayerTap, PlayerIdentityTrigger or the PQV opener), audited in the 2026-11-14 tap sweep",
  "web-next/src/components/TodayGlance.tsx": "exempt: the trade idea card is ONE link that opens the idea in Trade Hub; its avatars and names are the card's content inside that single tap target (a picker row rule), not separate player taps",
  "mobile/src/components/TodayGlance.tsx": "exempt: the trade idea card is ONE link that opens the idea in Trade Hub; its avatars and names are the card's content inside that single tap target (a picker row rule), not separate player taps",
  "web-next/src/components/NewsContent.tsx": "draws its own identity markup and wires its own tap (PlayerTap, PlayerIdentityTrigger or the PQV opener), audited in the 2026-11-14 tap sweep",
  "web-next/src/components/PercentileExplorerSheet.tsx": "draws its own identity markup and wires its own tap (PlayerTap, PlayerIdentityTrigger or the PQV opener), audited in the 2026-11-14 tap sweep",
  "web-next/src/components/PlayerCardKit.tsx": "draws its own identity markup and wires its own tap (PlayerTap, PlayerIdentityTrigger or the PQV opener), audited in the 2026-11-14 tap sweep",
  "web-next/src/components/PlayerCompareContent.tsx": "draws its own identity markup and wires its own tap (PlayerTap, PlayerIdentityTrigger or the PQV opener), audited in the 2026-11-14 tap sweep",
  "web-next/src/components/PlayerHeroHeader.tsx": "exempt: the player's own profile hero (already on that player)",
  "web-next/src/components/PlayerListRow.tsx": "draws its own identity markup and wires its own tap (PlayerTap, PlayerIdentityTrigger or the PQV opener), audited in the 2026-11-14 tap sweep",
  "web-next/src/components/PlayerRow.tsx": "draws its own identity markup and wires its own tap (PlayerTap, PlayerIdentityTrigger or the PQV opener), audited in the 2026-11-14 tap sweep",
  "web-next/src/components/SimDraftBar.tsx": "draws its own identity markup and wires its own tap (PlayerTap, PlayerIdentityTrigger or the PQV opener), audited in the 2026-11-14 tap sweep",
  "web-next/src/components/SimDraftOverview.tsx": "draws its own identity markup (the fixed Just-drafted card layout); the whole card button wires the tap (onOpenPlayer opens the player) and the avatar inside is nonInteractive",
  "web-next/src/components/SimDraftGrid.tsx": "draws its own identity markup and wires its own tap (PlayerTap, PlayerIdentityTrigger or the PQV opener), audited in the 2026-11-14 tap sweep",
  "web-next/src/components/SimDraftHero.tsx": "draws its own identity markup and wires its own tap (PlayerTap, PlayerIdentityTrigger or the PQV opener), audited in the 2026-11-14 tap sweep",
  "web-next/src/components/SimGameParts.tsx": "draws its own identity markup and wires its own tap (PlayerTap, PlayerIdentityTrigger or the PQV opener), audited in the 2026-11-14 tap sweep",
  "web-next/src/components/SuggestedDrop.tsx": "draws its own identity markup and wires its own tap (PlayerTap, PlayerIdentityTrigger or the PQV opener), audited in the 2026-11-14 tap sweep",
  "web-next/src/components/TradeIdeaCard.tsx": "draws its own identity markup and wires its own tap (PlayerTap, PlayerIdentityTrigger or the PQV opener), audited in the 2026-11-14 tap sweep",
  "web-next/src/components/TradePickerSheet.tsx": "draws its own identity markup and wires its own tap (PlayerTap, PlayerIdentityTrigger or the PQV opener), audited in the 2026-11-14 tap sweep",
  "web-next/src/components/WaiversContent.tsx": "draws its own identity markup and wires its own tap (PlayerTap, PlayerIdentityTrigger or the PQV opener), audited in the 2026-11-14 tap sweep",
  "web-next/src/components/WatchListCard.tsx": "draws its own identity markup and wires its own tap (PlayerTap, PlayerIdentityTrigger or the PQV opener), audited in the 2026-11-14 tap sweep",
  "web-next/src/components/ui/MatchupModule.tsx": "draws its own identity markup and wires its own tap (PlayerTap, PlayerIdentityTrigger or the PQV opener), audited in the 2026-11-14 tap sweep",
};

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
    if (depth > 0 && (c === '"' || c === "'" || c === "`")) { quote = c; continue; }
    if (depth === 0 && (c === '"' || c === "'")) { quote = c; continue; }
    if (c === "{") depth++;
    else if (c === "}") depth--;
    else if (c === ">" && depth === 0 && src[i - 1] !== "=") return i + 1;
  }
  return src.length;
}

function lineOf(src, idx) {
  return src.slice(0, idx).split("\n").length;
}

export function checkSource(rel, src) {
  const errors = [];
  // 1 + 3: template tags.
  for (const name of TEMPLATES) {
    const re = new RegExp(`<${name}(?=[\\s/>])`, "g");
    let m;
    while ((m = re.exec(src))) {
      const end = tagEnd(src, m.index);
      const tag = src.slice(m.index, end);
      const off = /nonInteractive(=|\s|\/|>)/.exec(tag);
      if (off) {
        const lit = /nonInteractive=(?:"([^"]*)"|'([^']*)'|\{\s*(?:"([^"]*)"|'([^']*)'|`([^`]*)`)\s*\}|\{[^}]*\?\s*(?:"([^"]*)"|'([^']*)')[^}]*\})/.exec(tag);
        const ident = /nonInteractive=\{\s*([A-Za-z_][\w]*)\s*(?:\?\?[^}]*)?\}/.exec(tag);
        if (/nonInteractive=\{\s*[\w.]*nonInteractive\s*\}/.test(tag)) continue; // prop pass-through inside a template
        let reason = lit ? lit.slice(1).find((x) => x != null) : null;
        if (reason == null && ident) {
          const def = new RegExp(`(?:const|let)\\s+${ident[1]}\\s*=[^;]*?["']([^"']{12,})["']`).exec(src);
          reason = def ? def[1] : null;
        }
        if (reason == null || reason.trim().length < 12) errors.push(`${rel}:${lineOf(src, m.index)} <${name}> nonInteractive needs a reason string of 12+ characters`);
      }
    }
  }
  // 5: avatars carry identity.
  if (!/\/(PlayerAvatar|TeamAvatar)\.tsx$/.test(rel) && !String(RAW_ALLOWLIST[rel] ?? "").startsWith("exempt:")) {
    for (const [tagName, props] of [["PlayerAvatar", ["name"]], ["TeamAvatar", ["name"]]]) {
      const re = new RegExp(`<${tagName}(?=[\\s/>])`, "g");
      let m;
      while ((m = re.exec(src))) {
        const tag = src.slice(m.index, tagEnd(src, m.index));
        if (!props.some((pr) => new RegExp(`\\b${pr}=`).test(tag))) errors.push(`${rel}:${lineOf(src, m.index)} <${tagName}> needs ${props.map((x) => `\`${x}\``).join(" or ")} so a missing photo falls back to a monogram, not an empty circle`);
      }
    }
  }
  for (const c of CONTAINERS) {
    const re = new RegExp(`<${c}(?=[\\s>])`, "g");
    let m;
    while ((m = re.exec(src))) {
      const end = tagEnd(src, m.index);
      if (src[end - 2] === "/") continue; // self-closing
      // find the matching close tag
      let depth = 1;
      const open = new RegExp(`<${c}(?=[\\s>])|</${c}>`, "g");
      open.lastIndex = end;
      let n;
      let closeIdx = -1;
      while ((n = open.exec(src))) {
        if (n[0].startsWith("</")) depth--;
        else if (src[tagEnd(src, n.index) - 2] !== "/") depth++;
        if (depth === 0) { closeIdx = n.index; break; }
      }
      if (closeIdx < 0) continue;
      const inner = src.slice(end, closeIdx);
      for (const name of TEMPLATES) {
        if (name === "PlayerAccordionRow") continue; // a row inside a tap target is a different (list) pattern
        const tre = new RegExp(`<${name}(?=[\\s/>])`, "g");
        let t;
        while ((t = tre.exec(inner))) {
          const tag = inner.slice(t.index, tagEnd(inner, t.index));
          if (!/nonInteractive/.test(tag) && !/\bonOpen\b|\bonPress\b|\bquick\b/.test(tag)) {
            errors.push(`${rel}:${lineOf(src, end + t.index)} <${name}> sits inside <${c}> without nonInteractive (nested tap targets)`);
          }
        }
      }
    }
  }
  return errors;
}

export function run() {
  const errors = [];
  for (const f of TEMPLATE_FILES) {
    const src = readFileSync(path.join(ROOT, f), "utf8");
    if (!/PlayerTap|PickTap/.test(src)) errors.push(`${f}: must route through PlayerTap / PickTap (the default tap was removed)`);
  }
  const rawUsers = [];
  for (const tree of TREES) {
    for (const file of walk(path.join(ROOT, tree))) {
      const rel = path.relative(ROOT, file);
      const src = readFileSync(file, "utf8");
      errors.push(...checkSource(rel, src));
      if (/<(PlayerAvatar|PlayerName)[\s/>]/.test(src) && !/\/(PlayerAvatar|PlayerName|PlayerAvatarSlot|CompactPlayerCard|PlayerAccordionRow|PlayerIdentity)\.tsx$/.test(rel)) rawUsers.push(rel);
    }
  }
  for (const rel of rawUsers) {
    if (!RAW_ALLOWLIST[rel]) errors.push(`${rel}: draws a raw <PlayerAvatar>/<PlayerName>; use a shared player template or add it to RAW_ALLOWLIST in scripts/check_player_tap.mjs with a reason`);
  }
  for (const rel of Object.keys(RAW_ALLOWLIST)) {
    if (!rawUsers.includes(rel)) errors.push(`${rel}: listed in RAW_ALLOWLIST but no longer draws a raw avatar/name; remove it`);
  }
  return errors;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const errors = run();
  if (errors.length) {
    console.error(`player tap check failed (${errors.length}):\n` + errors.map((e) => `  - ${e}`).join("\n"));
    process.exit(1);
  }
  console.log("player tap check passed");
}
