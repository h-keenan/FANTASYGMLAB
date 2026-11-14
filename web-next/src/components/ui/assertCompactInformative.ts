import { MIN_COLLAPSED_CHARS } from "@/lib/moduleTemplates";

/**
 * Lint-style assertion for page tests (docs/ui-patterns.md, "Module templates"): every COLLAPSED compact module on the
 * page must say something. CompactModule's header button is named "Title: summary. Expand", so the summary is what sits
 * between the first ": " and the final ". Expand". A header with no summary is named "Title. Expand" and fails.
 * Returns the problems (empty when the page is clean) so a test can `expect(problems).toEqual([])`.
 */
export function collapsedModuleProblems(root: ParentNode, min: number = MIN_COLLAPSED_CHARS): string[] {
  const problems: string[] = [];
  const buttons = Array.from(root.querySelectorAll<HTMLElement>('button[aria-expanded="false"][aria-label$=". Expand"]'));
  for (const button of buttons) {
    const label = button.getAttribute("aria-label") ?? "";
    const body = label.slice(0, -". Expand".length);
    const at = body.indexOf(": ");
    const title = at === -1 ? body : body.slice(0, at);
    const summary = at === -1 ? "" : body.slice(at + 2);
    if (summary.trim().length < min) problems.push(`"${title}" collapsed shows ${summary.trim().length} characters (needs ${min}): "${summary}"`);
  }
  return problems;
}

/** Every `<CompactModule` JSX opening tag in `source`, as its props text (brace-aware, so `=>` and `{}` are skipped). */
export function compactModuleOpeningTags(source: string): string[] {
  const tags: string[] = [];
  let from = 0;
  for (;;) {
    const at = source.indexOf("<CompactModule", from);
    if (at === -1) return tags;
    let depth = 0;
    let i = at + "<CompactModule".length;
    let quote: string | null = null;
    for (; i < source.length; i += 1) {
      const c = source[i];
      if (quote) {
        if (c === quote && source[i - 1] !== "\\") quote = null;
        continue;
      }
      if ((c === '"' || c === "'" || c === "`") && depth >= 0) quote = c;
      else if (c === "{") depth += 1;
      else if (c === "}") depth -= 1;
      else if (c === ">" && depth === 0 && source[i - 1] !== "=") break;
    }
    tags.push(source.slice(at, i));
    from = i;
  }
}
