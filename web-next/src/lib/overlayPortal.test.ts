// Guard: a full-viewport overlay must go through a shared shell (ui/Sheet, PopupShell, StoryCarousel, TradePickerSheet,
// SimSheet) or <OverlayPortal>. A hand-rolled `position: fixed` layer rendered in the tree is boxed into any ancestor with
// a transform / filter / backdrop-filter and ends up anchored to the page instead of the viewport.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

const SRC = join(__dirname, "..");

function walk(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) walk(full, out);
    else if (/\.tsx$/.test(name) && !/\.test\./.test(name)) out.push(full);
  }
  return out;
}

const FIXED = /\bfixed\b[^"'`]*\binset-0\b|\binset-0\b[^"'`]*\bfixed\b|position:\s*["']?fixed|pqv-backdrop|ui-sheet-backdrop|aria-modal/;
const ROUTED = /createPortal|<OverlayPortal|<PopupShell|<Sheet\b/;

// Files that ARE the shared shells (they portal themselves, checked below) or that only mention the pattern in prose/previews.
const SHELLS = new Set(["components/ui/Sheet.tsx", "components/PopupShell.tsx", "components/ui/OverlayPortal.tsx"]);
const PREVIEW_ONLY = new Set(["app/design/DesignSystemContent.tsx"]);
// Fixed page chrome that is not an overlay (no scrim, never modal): the desktop side navigation.
const CHROME = new Set(["components/DesktopSidebar.tsx"]);

describe("overlay guard", () => {
  const files = walk(SRC).map((f) => ({ path: relative(SRC, f), text: readFileSync(f, "utf8") }));

  it("every fixed/modal overlay is portaled through a shared primitive", () => {
    const offenders = files
      .filter((f) => !PREVIEW_ONLY.has(f.path) && !CHROME.has(f.path))
      .filter((f) => FIXED.test(f.text.replace(/\/\*[\s\S]*?\*\/|^\s*\/\/.*$|\{\/\*[\s\S]*?\*\/\}/gm, "")))
      .filter((f) => !ROUTED.test(f.text))
      .map((f) => f.path);
    expect(offenders).toEqual([]);
  });

  it("the shared shells portal to document.body", () => {
    for (const path of SHELLS) {
      const text = files.find((f) => f.path === path)?.text ?? "";
      expect(text, path).toMatch(/createPortal\([\s\S]*document\.body|createPortal\(children, document\.body\)/);
    }
  });
});
