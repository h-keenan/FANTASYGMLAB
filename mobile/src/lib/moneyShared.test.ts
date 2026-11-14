import assert from 'node:assert/strict';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, resolve } from 'node:path';
import { test } from 'node:test';

import { formatMoney, formatMoneyRange, splitMoney } from './money.ts';

// Dollar amounts are built by lib/money.ts and painted by <Money> (colors.money).
const SRC = resolve(process.cwd(), 'src');
const ALLOWED = new Set(['lib/money.ts', 'components/Money.tsx', 'lib/privacyMask.ts']);
const RAW_MONEY = /\$\$\{|["'`]\$\d/;

function walk(dir: string, out: string[] = []): string[] {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (/\.(ts|tsx)$/.test(name) && !/\.test\./.test(name)) out.push(p);
  }
  return out;
}

test('no raw money formatting outside the shared module', () => {
  const offenders = walk(SRC)
    .filter((f) => !ALLOWED.has(f.slice(SRC.length + 1)))
    .filter((f) => readFileSync(f, 'utf8').split('\n').some((l) => !/^\s*(\/\/|\*|\/\*)/.test(l) && RAW_MONEY.test(l)))
    .map((f) => f.slice(SRC.length + 1));
  assert.deepEqual(offenders, []);
});

test('formats and splits amounts', () => {
  assert.equal(formatMoney(81), '$81');
  assert.equal(formatMoneyRange(8, 12), '$8–$12');
  assert.equal(splitMoney('of $81 remaining')[1].money, true);
  assert.equal(splitMoney('42.5 pts').some((s) => s.money), false);
});
