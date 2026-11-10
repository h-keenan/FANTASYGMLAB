import assert from 'node:assert/strict';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { test } from 'node:test';

// `colors` exported from theme.ts is the static DARK palette. A component that
// reads it at module scope never follows the theme toggle (PostureChip and
// IdeaPosture did exactly that and rendered dark text on light surfaces). Use
// `const { colors } = useThemeMode()` + a createStyles(colors) factory instead.
// Share cards are intentionally fixed-palette (they render to images).
const SRC = 'src'; // npm test runs from mobile/
const ALLOWED = /(ShareCard|ShareCardChrome)/;

function walk(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) walk(full, out);
    else if (/\.(ts|tsx)$/.test(name) && !/\.test\./.test(name)) out.push(full);
  }
  return out;
}

test('no component reads the static dark `colors` palette from theme (use useThemeMode)', () => {
  const offenders: string[] = [];
  for (const file of walk(SRC)) {
    const rel = relative(SRC, file);
    if (rel === 'theme.ts' || ALLOWED.test(rel)) continue;
    const src = readFileSync(file, 'utf8');
    if (/import\s*\{[^}]*\bcolors\b[^}]*\}\s*from\s*'(\.\.?\/)+theme'/.test(src)) offenders.push(rel);
  }
  assert.deepEqual(offenders, []);
});
