// Run with: node --experimental-strip-types --test src/lib/typographyMinimums.test.ts
// Guard: no new sub-minimum fontSize literals, and theme typography roles
// honor their minimums. Parses source text (theme.ts imports react-native,
// which plain Node cannot load).
import test from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const SRC = join(dirname(fileURLToPath(import.meta.url)), '..');
const FLOOR = 12;

// Fixed-size surfaces where small text is intentional: share-card images are
// rendered at a fixed canvas size, GmOrb/ring/gauge text sits inside fixed
// graphics, and DesignScreen is an internal token gallery.
const EXEMPT = /ShareCard|GmOrb\.tsx|DesignScreen\.tsx|CircularProgressRing\.tsx|OverallRatingBadge\.tsx|MetricCard\.tsx|\.test\.ts/;

function walk(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (/\.tsx?$/.test(name)) out.push(p);
  }
  return out;
}

test('no fontSize literal below the floor outside exempt files', () => {
  const offenders: string[] = [];
  for (const file of walk(SRC)) {
    if (EXEMPT.test(file) || file.endsWith('theme.ts')) continue;
    readFileSync(file, 'utf8')
      .split('\n')
      .forEach((line, i) => {
        for (const m of line.matchAll(/fontSize:\s*(\d+(?:\.\d+)?)\b/g)) {
          if (Number(m[1]) < FLOOR) offenders.push(`${file.replace(SRC, 'src')}:${i + 1} fontSize ${m[1]}`);
        }
      });
  }
  assert.deepEqual(offenders, [], `fontSize below ${FLOOR}; use a typography role or >= ${FLOOR}`);
});

test('theme typography roles meet their minimum sizes', () => {
  const theme = readFileSync(join(SRC, 'theme.ts'), 'utf8');
  const min = /TYPOGRAPHY_MINIMUMS = \{([\s\S]*?)\} as const/.exec(theme);
  assert.ok(min, 'TYPOGRAPHY_MINIMUMS present');
  for (const m of min[1].matchAll(/(\w+):\s*(\d+(?:\.\d+)?)/g)) {
    const role = new RegExp(`^  ${m[1]}: \\{ fontSize: (\\d+(?:\\.\\d+)?)`, 'm').exec(theme);
    assert.ok(role, `typography.${m[1]} defined`);
    assert.ok(Number(role[1]) >= Number(m[2]), `typography.${m[1]} ${role[1]} < min ${m[2]}`);
  }
});
