#!/usr/bin/env node
// Guard (accessibility audit 2026-11): an icon-only pressable in the app must name itself for VoiceOver / TalkBack.
// A <Pressable>, <PressableScale>, <TouchableOpacity> or <TouchableHighlight> whose children hold an icon
// (<Ionicons>, <Icon>, <MaterialIcons>, <Feather>, ...) and no text (<Text>, <AppText>, {expression text}) needs an
// accessibilityLabel (or accessibilityLabelledBy) on the opening tag. A pressable that is intentionally decorative may carry
// `a11y-ok: reason` in a comment on the line above or inside the opening tag.
//
// Usage: node scripts/check_app_a11y_labels.mjs   (exit 1 on any violation)
import { readdirSync, readFileSync, statSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const TREE = path.join(ROOT, "mobile/src");
const OPEN = /<(Pressable|PressableScale|TouchableOpacity|TouchableHighlight|TouchableWithoutFeedback)\b/g;
const ICON = /<(Ionicons|MaterialIcons|MaterialCommunityIcons|Feather|FontAwesome\d?|AntDesign|Entypo|Icon|AppIcon|SvgIcon)\b/;
const TEXTY = /<(Text|AppText|RNText|Animated\.Text|StatValue|ValueStat|Chip|Badge|PositionBadge|TierBadge|PlayerAvatar|Avatar|TeamAvatar)\b/;
const HIDDEN = /accessibilityElementsHidden|importantForAccessibility="no/;
const LABEL = /accessibilityLabel(ledBy)?\s*=/;

function* walk(dir) {
  for (const name of readdirSync(dir)) {
    if (name === "node_modules" || name.startsWith(".")) continue;
    const full = path.join(dir, name);
    if (statSync(full).isDirectory()) yield* walk(full);
    else if (/\.tsx$/.test(name) && !/\.test\./.test(name)) yield full;
  }
}

// End index of the JSX opening tag that starts at `start` (handles `=>` and braces inside attributes).
function openingTagEnd(src, start) {
  let depth = 0;
  for (let i = start; i < src.length; i += 1) {
    const c = src[i];
    if (c === "{") depth += 1;
    else if (c === "}") depth -= 1;
    else if (c === ">" && depth === 0 && src[i - 1] !== "=") return i;
  }
  return -1;
}

const bad = [];
for (const file of walk(TREE)) {
  const src = readFileSync(file, "utf8");
  for (const m of src.matchAll(OPEN)) {
    const tag = m[1];
    const end = openingTagEnd(src, m.index);
    if (end === -1) continue;
    const opening = src.slice(m.index, end + 1);
    if (opening.endsWith("/>")) continue; // self-closing: no children to be icon-only
    const closeIdx = src.indexOf(`</${tag}>`, end);
    if (closeIdx === -1) continue;
    const children = src.slice(end + 1, closeIdx);
    if (!ICON.test(children) || TEXTY.test(children) || />\s*[A-Za-z][^<{}]*</.test(children)) continue;
    if (LABEL.test(opening) || HIDDEN.test(opening) || /a11y-ok/.test(opening)) continue;
    const line = src.slice(0, m.index).split("\n").length;
    const prev = src.split("\n")[line - 2] || "";
    if (/a11y-ok/.test(prev)) continue;
    bad.push(`${path.relative(ROOT, file)}:${line}: <${tag}> holds only an icon and has no accessibilityLabel`);
  }
}
if (bad.length) {
  console.error(`Icon-only pressables without an accessibilityLabel (${bad.length}):\n${bad.join("\n")}`);
  process.exit(1);
}
console.log("check_app_a11y_labels: ok");
