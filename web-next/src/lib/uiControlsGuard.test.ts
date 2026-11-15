import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";

/** UI consistency audit 4 (docs/audits/2026-11-ui-consistency-audit-4.md): controls come from the shared pieces. */
const WEB_ROOT = path.resolve(__dirname, "..");
const APP_ROOT = path.resolve(__dirname, "../../../mobile/src");

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name !== "node_modules") walk(full, out);
    } else if (/\.tsx$/.test(entry.name) && !/\.test\.tsx$/.test(entry.name)) out.push(full);
  }
  return out;
}

describe("ui controls guard (audit 4)", () => {
  it("every <select> is the shared <Select> or carries .glass-input / .filter-select / the chip style (44px, control radius)", () => {
    const bad: string[] = [];
    for (const file of walk(WEB_ROOT)) {
      if (/components\/Input\.tsx$|app\/design\//.test(file)) continue;
      const src = readFileSync(file, "utf8");
      for (const m of src.matchAll(/<select\b[\s\S]{0,500}/g)) {
        if (!/glass-input|filter-select|filter-input|chipStyle/.test(m[0])) bad.push(`${path.relative(WEB_ROOT, file)}: ${m[0].replace(/\s+/g, " ").slice(0, 90)}`);
      }
    }
    expect(bad).toEqual([]);
  });

  it("a disabled filled Button keeps a hairline edge on web and app (never a loose-looking label)", () => {
    expect(readFileSync(path.join(WEB_ROOT, "components/Button.tsx"), "utf8")).toMatch(/disabled && \(variant === "primary"[^)]*\) \? \{ boxShadow: "inset 0 0 0 var\(--border-width-default\) var\(--color-border-strong\)"/);
    expect(readFileSync(path.join(APP_ROOT, "components/Button.tsx"), "utf8")).toMatch(/primaryDisabled: \{ backgroundColor: mutedFill, borderWidth: 1, borderColor: colors\.borderStrong \}/);
  });
});
