import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { test } from 'node:test';

/**
 * Web/app design-token sync. theme.ts imports react-native, so it is read as
 * text; globals.css is the source of truth for the shared semantic palette.
 * Intentional app-only divergences (neutral surface ramp, text greys, glass)
 * are documented in docs/app-web-parity-audit.md and are not asserted here.
 */
const css = readFileSync(resolve(process.cwd(), '../web-next/src/app/globals.css'), 'utf8');
const theme = readFileSync(resolve(process.cwd(), 'src/theme.ts'), 'utf8');

const lightStart = css.indexOf('@media (prefers-color-scheme: light)');
const darkCss = css.slice(css.indexOf(':root {'), lightStart);
const lightCss = css.slice(lightStart, css.indexOf('color-scheme: light;', lightStart));

function cssVar(block: string, name: string): string {
  const m = block.match(new RegExp(`--${name}:\\s*([^;]+);`));
  assert.ok(m, `--${name} missing in globals.css`);
  return m[1].trim().toLowerCase().replace(/\s+/g, '');
}

function themeBlock(name: 'darkColors' | 'lightColors'): string {
  const start = theme.indexOf(`const ${name} = {`);
  assert.ok(start >= 0, `${name} missing`);
  return theme.slice(start, theme.indexOf('\n};', start));
}

function themeColor(block: string, key: string): string {
  const m = block.match(new RegExp(`^\\s{2}${key}:\\s*'([^']+)'`, 'm'));
  assert.ok(m, `${key} missing in theme.ts`);
  return m[1].trim().toLowerCase().replace(/\s+/g, '');
}

const PAIRS: Array<[string, string]> = [
  ['accent', 'color-accent'],
  ['accentStrong', 'color-accent-strong'],
  ['onAccent', 'color-on-accent'],
  ['danger', 'color-danger'],
  ['success', 'color-success'],
  ['warning', 'color-warning'],
  ['premiumFill', 'color-premium-fill'],
  ['onPremium', 'color-on-premium'],
];

for (const [mode, cssBlock, themeName] of [
  ['dark', darkCss, 'darkColors'],
  ['light', lightCss, 'lightColors'],
] as const) {
  test(`${mode} semantic colors match web globals.css`, () => {
    const block = themeBlock(themeName);
    for (const [key, variable] of PAIRS) {
      assert.equal(themeColor(block, key), cssVar(cssBlock, variable), `${mode} ${key} vs --${variable}`);
    }
  });
}

test('position hues match web --color-position-*', () => {
  for (const pos of ['qb', 'rb', 'wr', 'te', 'k', 'dl', 'lb', 'db']) {
    const m = theme.match(new RegExp(`^\\s{2}${pos.toUpperCase()}:\\s*'(#[0-9a-fA-F]{6})'`, 'm'));
    assert.ok(m, `position ${pos}`);
    assert.equal(m[1].toLowerCase(), cssVar(darkCss, `color-position-${pos}`));
  }
});

test('radii and spacing scales match web tokens', () => {
  const num = (block: string, name: string) => Number(cssVar(block, name).replace('px', ''));
  const scale = (obj: string, key: string) => {
    const start = theme.indexOf(`export const ${obj} = {`);
    const m = theme.slice(start, theme.indexOf('};', start)).match(new RegExp(`\\b${key}:\\s*(\\d+)`));
    assert.ok(m, `${obj}.${key}`);
    return Number(m[1]);
  };
  for (const k of ['xs', 'sm', 'md', 'lg', 'xl']) assert.equal(scale('spacing', k), num(darkCss, `space-${k}`), `space-${k}`);
  for (const k of ['sm', 'md', 'lg']) assert.equal(scale('radii', k), num(darkCss, `radius-${k}`), `radius-${k}`);
});
