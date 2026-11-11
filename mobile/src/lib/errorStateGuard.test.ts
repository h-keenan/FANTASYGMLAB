import assert from 'node:assert/strict';
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { test } from 'node:test';

/**
 * Guard: a load failure is shown with the shared ErrorState (danger icon,
 * plain-language title, one "Try again" retry, HelpLink), never a hand-rolled
 * <AppText>Couldn't load ...</AppText> line. A true partial-failure note that
 * is not a retryable load error can be listed in ALLOWED with a reason.
 */
const ALLOWED: Record<string, string> = {
  // Partial note inside a section whose other data is still shown.
  'screens/PortfolioScreen.tsx': 'partial league load note, rest of the page is current',
  // Secondary caption under the Waivers watchlist tab, not the page load.
  'screens/WaiversScreen.tsx': 'secondary caption for the watchlist strip',
};

const FAILURE_COPY = /(Couldn['’]t load|Could not load|Failed to load|Unable to load)/;
// JSX text or template literal rendered inside an AppText.
const HAND_ROLLED = /<AppText[^>]*>\s*(\{\s*[`'"])?[^<{}]*?(Couldn['’]t load|Could not load|Failed to load|Unable to load)/;

function walk(dir: string, out: string[] = []): string[] {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) walk(path, out);
    else if (/\.tsx$/.test(entry.name) && !/\.test\./.test(entry.name)) out.push(path);
  }
  return out;
}

test('no hand-rolled "Couldn\'t load" text; use ErrorState', () => {
  const root = join(import.meta.dirname, '..');
  const offenders: string[] = [];
  for (const file of walk(join(root, 'screens')).concat(walk(join(root, 'components')))) {
    const rel = file.slice(root.length + 1);
    if (ALLOWED[rel]) continue;
    const source = readFileSync(file, 'utf8');
    if (!FAILURE_COPY.test(source)) continue;
    // Match across the JSX line so multi-line AppText children are caught too.
    if (HAND_ROLLED.test(source.replace(/\n\s*/g, ' '))) offenders.push(rel);
  }
  assert.deepEqual(offenders, [], `Use <ErrorState> instead of hand-rolled load-failure text: ${offenders.join(', ')}`);
});

test('ErrorState keeps a single retry label', () => {
  const source = readFileSync(join(import.meta.dirname, '..', 'components', 'ErrorState.tsx'), 'utf8');
  assert.match(source, /retryLabel = 'Try again'/);
});
