/**
 * Forces the page's light or dark palette regardless of the OS setting.
 * The app's themes are pure `@media (prefers-color-scheme: ...)` blocks, so
 * the override rewrites each such media rule's condition in place:
 *   force "light" -> light rules always match, dark rules never
 *   force "dark"  -> light rules never match, dark rules always
 *   "auto"        -> original conditions restored
 * No CSS is duplicated, so the preview can never drift from the real tokens.
 */
type MediaRuleLike = { media: { mediaText: string }; cssRules?: CSSRuleList };

const originals = new WeakMap<object, string>();

function walk(rules: CSSRuleList, visit: (rule: MediaRuleLike) => void) {
  for (const rule of Array.from(rules)) {
    const maybeMedia = rule as unknown as MediaRuleLike;
    if (maybeMedia.media && /prefers-color-scheme/.test(maybeMedia.media.mediaText)) {
      visit(maybeMedia);
    }
    const nested = (rule as unknown as { cssRules?: CSSRuleList }).cssRules;
    if (nested) walk(nested, visit);
  }
}

export type ThemeChoice = "auto" | "light" | "dark";

export function applyThemeOverride(choice: ThemeChoice): void {
  if (typeof document === "undefined") return;
  for (const sheet of Array.from(document.styleSheets)) {
    let rules: CSSRuleList;
    try {
      rules = sheet.cssRules;
    } catch {
      continue; // cross-origin sheet
    }
    walk(rules, (rule) => {
      if (!originals.has(rule)) originals.set(rule, rule.media.mediaText);
      const original = originals.get(rule) ?? rule.media.mediaText;
      if (choice === "auto") {
        rule.media.mediaText = original;
        return;
      }
      const isLightRule = /prefers-color-scheme:\s*light/.test(original);
      const matches = choice === "light" ? isLightRule : !isLightRule;
      rule.media.mediaText = matches ? "all" : "not all";
    });
  }
  document.documentElement.style.colorScheme = choice === "auto" ? "" : choice;
}
