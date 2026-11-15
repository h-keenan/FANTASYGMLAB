#!/usr/bin/env node
// Module status board generator. Re-runnable, deterministic, no network:
//   node scripts/module_status.mjs            -> writes docs/audits/module-status-board.md
//   node scripts/module_status.mjs --check    -> exits 1 when the committed board is stale (not wired into CI)
// Scans web-next/src/components (+ ui/) and mobile/src/components + screens, and classifies every page module:
//   1 on a shared template and compliant, 2 on a shared template with gaps, 3 one-off / legacy (with effort S/M/L by size).
// Columns (the standing UI rules): compact+expand, PFPs, names never ellipsized, tappable players/picks, skeleton, presence
// animation, green money, gold-only-premium, letter grades (Sim), chevron rule, 44px targets, web/app parity.
// Source-scan heuristics: a cell is "ok", "GAP", or "-" (not applicable to this file). They flag where to look, they do not
// replace a visual check (docs/audits/2026-11-ui-consistency-audit-4.md). Keep the rules below in sync with docs/ui-patterns.md.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const OUT = path.join(ROOT, "docs/audits/module-status-board.md");

const TEMPLATES_WEB = ["CompactModule", "PlayerAccordionRow", "CompactPlayerCard", "TradeCompactCard", "StatusHeader", "StatStripModule", "LinkModule", "Hero", "RankRow", "StructuredRow", "RecapCard", "StoryCarousel", "Sheet", "SimFold"];
const TEMPLATE_RE = new RegExp(`\\b(${TEMPLATES_WEB.join("|")})\\b`);
const PLAYER_RE = /\bplayer(s|_id|Id)?\b|\.player\b|PlayerRow|roster/i;
const NAME_RE = /\.name\b|player_name|playerName/;
const PFP_OK = /PlayerAvatar|PlayerIdentity|PlayerAccordionRow|CompactPlayerCard|TradeAssetRow|PlayerAvatarSlot|PlayerRow|SimPlayerLine|SimPlayerChip|PlayerHeadshot|TradeCompactCard|PickAvatar/;
const TAP_OK = /PlayerTap|PickTap|openPlayer|usePlayerQuickView|onOpenPlayer|PlayerAccordionRow|CompactPlayerCard|TradeCompactCard|SimPlayerNameTap|PlayerIdentity|PlayerRow|onOpen\b/;
const SKELETON_OK = /Skeleton/;
const LOADING_BAD = />\s*Loading|'Loading[.…]|"Loading[.…]|ActivityIndicator/;
const PRESENCE_OK = /Presence|Collapse|MotionIn|PresenceList|PresenceSwap|CompactModule|PlayerAccordionRow|FadeIn|LayoutAnimation|Animated\./;
const TOGGLE_RE = /useState\((false|true)\)|\bopen\s*(&&|\?)|\bexpanded\b|\bshow[A-Z]\w*\s*(&&|\?)/;
const MONEY_USE = /\$\$\{|>\s*\$\{|["'`]\$["'`]\s*\+|["'`]\$\d|FAABGuidance|FaabRange|formatFaab/;
const MONEY_OK = /\bMoney\b/;
const GOLD_RE = /--color-premium|--color-action\b|premium-fill|colors\.premium|colors\.premiumFill|var\(--color-action/;
const PREMIUM_FILE = /Premium|Paywall|Pro[A-Z]|Upgrade|Pricing|Founder|Billing|Limit|Trophy|Achievement|Champion|Crown|Prestige|Trial|Entitlement|Share|FirstValue|NavPro|Sim|LetterGrade|PlayerBadge|Button|CompactModule|ModuleTemplates|Hero|Orb|Pill/;
const OVR_RE = /overall_rating|OvrGauge|OverallRating|trade value|tradeValue|\.score\b/i;
const CHEVRON_RE = /›|▸|▶|chevron-forward|ChevronRight|chevron-right|&rsaquo;/;
const SMALL_TARGET_WEB = /<button[^>]*className="[^"]*\b(h-6|h-7|h-8|min-h-\[?(2\d|3\d)(px)?\]?)\b/;
const SMALL_TARGET_APP = /(minHeight|height):\s*(2\d|3\d)\b[^}]*\n?[^}]*/;

const PAGE_LEVEL = /Content$|Screen$|Card$|Panel$|Section$|Sections$|Board$|Strip$|Tab$|Summary$|Grid$|List$/;
const rel = (p) => path.relative(ROOT, p).split(path.sep).join("/");
function walk(dir, out = []) {
  if (!fs.existsSync(dir)) return out;
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, e.name);
    if (e.isDirectory()) {
      if (/node_modules|__tests__|design|seo|shareCard/.test(e.name)) continue;
      walk(full, out);
    } else if (/\.tsx$/.test(e.name) && !/\.test\.tsx$/.test(e.name)) out.push(full);
  }
  return out;
}
const strip = (s) => s.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");

const webDirs = [path.join(ROOT, "web-next/src/components")];
const appDirs = [path.join(ROOT, "mobile/src/components"), path.join(ROOT, "mobile/src/screens")];
const baseName = (f) => path.basename(f).replace(/\.tsx$/, "").replace(/Screen$/, "").replace(/Content$/, "");
const webFiles = webDirs.flatMap((d) => walk(d));
const appFiles = appDirs.flatMap((d) => walk(d));
const webBases = new Set(webFiles.map(baseName));
const appBases = new Set(appFiles.map(baseName));

// Which files render a template (usage), and which files import this module (is it used on a page at all?).
function analyse(file, platform) {
  const raw = fs.readFileSync(file, "utf8");
  const src = strip(raw);
  const lines = raw.split("\n").length;
  const name = path.basename(file).replace(/\.tsx$/, "");
  const isTemplateItself = /\/ui\//.test(file) || /^(CompactModule|ModuleTemplates|PlayerAccordionRow|CompactPlayerCard|TradeCompactCard|StatusHeader|RankRow|StructuredRow|RecapCard|StoryCarousel|Sheet|Presence)\b/.test(name);
  const usesTemplate = TEMPLATE_RE.test(src) && !isTemplateItself;
  const isSim = /^Sim|\/Sim/.test(name) || /Sim[A-Z]/.test(name);
  const hasPlayers = PLAYER_RE.test(src) && /name|Name|avatar|Avatar/.test(src);
  const hasNames = NAME_RE.test(src);
  const cells = {};
  cells.compact = isTemplateItself || usesTemplate ? "ok" : PAGE_LEVEL.test(name) && lines >= 100 ? "GAP" : "-";
  cells.pfp = !hasPlayers ? "-" : PFP_OK.test(src) ? "ok" : "GAP";
  const ellipsisBad = platform === "web"
    ? /\btruncate\b[^>]*>\s*\{[^{}]*(\.name|player_name|playerName)\b/.test(src)
    : /numberOfLines=\{\d\}[^>]*>\s*\{[^{}]*(\.name|player_name|playerName)\b/.test(src);
  cells.names = !hasNames ? "-" : ellipsisBad ? "GAP" : "ok";
  cells.tap = !hasPlayers ? "-" : TAP_OK.test(src) ? "ok" : "GAP";
  const loads = /\bloading\b|isLoading|useQuery|api\./.test(src);
  cells.skeleton = LOADING_BAD.test(src) ? "GAP" : SKELETON_OK.test(src) ? "ok" : loads && lines > 150 ? "GAP" : "-";
  cells.presence = PRESENCE_OK.test(src) ? "ok" : TOGGLE_RE.test(src) ? "GAP" : "-";
  cells.money = !MONEY_USE.test(src) ? "-" : MONEY_OK.test(src) ? "ok" : "GAP";
  cells.gold = !GOLD_RE.test(src) ? "ok" : PREMIUM_FILE.test(name) ? "ok" : "GAP";
  cells.grades = !isSim ? "-" : OVR_RE.test(src) && !/never|not\b|no numeric/i.test(raw.match(/overall_rating[^\n]*/)?.[0] ?? "x") && /overall_rating|OvrGauge|OverallRating/.test(src) ? "GAP" : "ok";
  cells.chevron = CHEVRON_RE.test(src) ? "GAP" : "ok";
  cells.target = (platform === "web" ? SMALL_TARGET_WEB.test(src) : /Pressable|PressableScale/.test(src) && /(minHeight|height):\s*(2\d|3\d)\b/.test(src) && !/hitSlop/.test(src)) ? "GAP" : "ok";
  const other = platform === "web" ? appBases : webBases;
  cells.parity = other.has(baseName(file)) ? "ok" : "GAP";
  return { file: rel(file), name, platform, lines, usesTemplate, isTemplateItself, isSim, cells };
}

function classify(m) {
  const gaps = Object.entries(m.cells).filter(([k, v]) => v === "GAP" && k !== "parity").map(([k]) => k);
  if (m.isTemplateItself) return { cls: 0, gaps };
  // Leaf pieces (badges, chips, small rows) are not page modules: listed in the matrix, not scored.
  const pageLevel = PAGE_LEVEL.test(m.name) && m.lines >= 100;
  if (!pageLevel && !m.usesTemplate) return { cls: "L", gaps };
  if (!m.usesTemplate) return { cls: 3, gaps };
  return { cls: gaps.length === 0 ? 1 : 2, gaps };
}
const effort = (lines) => (lines < 150 ? "S" : lines < 400 ? "M" : "L");

const all = [...webFiles.map((f) => analyse(f, "web")), ...appFiles.map((f) => analyse(f, "app"))].map((m) => ({ ...m, ...classify(m) }));
const COLS = [["compact", "compact+expand"], ["pfp", "PFPs"], ["names", "names"], ["tap", "tappable"], ["skeleton", "skeleton"], ["presence", "presence"], ["money", "green $"], ["gold", "gold=premium"], ["grades", "grades (Sim)"], ["chevron", "chevron rule"], ["target", "44px"], ["parity", "web/app parity"]];
const mark = (v) => (v === "ok" ? "ok" : v === "GAP" ? "**GAP**" : "-");

const count = (p, c) => all.filter((m) => m.platform === p && m.cls === c).length;
let md = `# Module status board

Generated by \`node scripts/module_status.mjs\` (source scan, deterministic; re-run after UI work). Cells are \`ok\`, **GAP** or \`-\` (not applicable). A GAP says where to look; confirm visually before fixing (rules: \`docs/ui-patterns.md\`, \`docs/audits/2026-11-ui-consistency-audit-4.md\`).

Classes: **1** on a shared template and compliant, **2** on a shared template with gaps, **3** still one-off / legacy (effort S under 150 lines, M under 400, L above), templates themselves (T) and leaf pieces (L: badges, chips, small rows, under 100 lines or not page-level) are listed in the matrix but not scored. Parity is informational (platform-specific files are expected) and does not change a class.

| Platform | Templates | 1 compliant | 2 template + gaps | 3 one-off / legacy | Leaf pieces (not scored) | Total files |
|---|---|---|---|---|---|---|
`;
for (const p of ["web", "app"]) md += `| ${p} | ${all.filter((m) => m.platform === p && m.cls === 0).length} | ${count(p, 1)} | ${count(p, 2)} | ${count(p, 3)} | ${all.filter((m) => m.platform === p && m.cls === "L").length} | ${all.filter((m) => m.platform === p).length} |\n`;

md += `\n## Gap totals per column (modules where the rule applies and fails)\n\n| Rule | web | app |\n|---|---|---|\n`;
for (const [k, label] of COLS) md += `| ${label} | ${all.filter((m) => m.platform === "web" && m.cells[k] === "GAP").length} | ${all.filter((m) => m.platform === "app" && m.cells[k] === "GAP").length} |\n`;

const RANKED = [
  ["1", "Trade builders: MultiTeamTradeContent / MultiTeamTradePanel", "L", "headline feature still off TradeCompactCard, no skeleton/PFP template; ship web + app together"],
  ["2", "Portfolio: PortfolioContent / PortfolioScreen", "L", "no PFP, tap or skeleton; rank badges and rows hand-rolled"],
  ["3", "LeagueRecapsContent (1111 lines) + app RecapScreen", "L", "biggest file, no module templates; split then move story bodies to RankRow/RecapCard"],
  ["4", "News: NewsContent / NewsScreen", "M", "daily-return surface, no compact modules or skeletons; roster-first feed row"],
  ["5", "Player Compare: PlayerCompareContent / PlayerCompareScreen", "L", "no templates on either platform; compare chips already on PlayerName"],
  ["6", "Alerts: AlertsContent / AlertsScreen", "M", "no CompactModule, app uses chevrons and gold"],
  ["7", "App Home / Teams / More screens", "L", "no PFP/tap/presence; the app's entry points"],
  ["8", "Account / Commissioner / Premium (web) and Commissioner / Onboarding / Login (app)", "M", "low traffic but look like another product"],
  ["9", "App PlayerDetailScreen (1960 lines)", "L", "split into tabs/modules; PFP and gold gaps"],
  ["10", "Sim tabs without CompactModule: SimGameLeague / SimGameTrades / SimGamePlayers / SimGameRecap", "M", "long uncollapsed lists (ui-pass-3 #9)"],
];
const section = (title, cls, withEffort) => {
  const rows = all.filter((m) => m.cls === cls).sort((a, b) => b.lines - a.lines || a.file.localeCompare(b.file));
  let s = `\n## ${title} (${rows.length})\n\n`;
  if (rows.length === 0) return s + "None.\n";
  s += `| Module | Platform | Lines |${withEffort ? " Effort |" : ""} Gaps |\n|---|---|---|${withEffort ? "---|" : ""}---|\n`;
  for (const m of rows) s += `| \`${m.file}\` | ${m.platform} | ${m.lines} |${withEffort ? ` ${effort(m.lines)} |` : ""} ${m.gaps.join(", ") || "-"} |\n`;
  return s;
};
md += `\n## Ranked remaining work (top 10, recommended order; edit RANKED in the script)\n\n| # | Module group | Effort | Why / first step |\n|---|---|---|---|\n${RANKED.map((r) => `| ${r.join(" | ")} |`).join("\n")}\n`;
md += section("Class 3: one-off / legacy", 3, true);
md += section("Class 2: on a shared template, with gaps", 2, false);
md += section("Class 1: shared template, compliant", 1, false);

md += `\n## Full matrix\n\n| Module | P | tpl | ${COLS.map((c) => c[1]).join(" | ")} | class |\n|---|---|---|${COLS.map(() => "---").join("|")}|---|\n`;
for (const m of [...all].sort((a, b) => a.platform.localeCompare(b.platform) || a.file.localeCompare(b.file))) {
  md += `| \`${m.file.replace(/^(web-next|mobile)\/src\//, "")}\` | ${m.platform[0]} | ${m.isTemplateItself ? "self" : m.usesTemplate ? "yes" : "no"} | ${COLS.map(([k]) => mark(m.cells[k])).join(" | ")} | ${m.cls === 0 ? "T" : m.cls} |\n`;
}

if (process.argv.includes("--check")) {
  const cur = fs.existsSync(OUT) ? fs.readFileSync(OUT, "utf8") : "";
  if (cur !== md) {
    console.error("module-status-board.md is stale: run node scripts/module_status.mjs");
    process.exit(1);
  }
  console.log("module-status-board.md is current");
} else {
  fs.writeFileSync(OUT, md);
  console.log(`wrote ${rel(OUT)}: ${all.length} modules`);
}
