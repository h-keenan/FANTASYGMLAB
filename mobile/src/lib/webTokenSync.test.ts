import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { test } from 'node:test';

/**
 * Web/app design-token sync. theme.ts imports react-native, so it is read as
 * text; globals.css is the source of truth for the shared semantic palette.
 * Intentional app-only divergences (glass, premium gold text, card cyan rim)
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
  // Neutral ramp (coridian_ 2026-10-27: "sync the palette to web").
  ['background', 'color-bg'],
  ['surface', 'color-surface-primary'],
  ['surfaceSolid', 'color-surface-primary'],
  ['border', 'color-border'],
  ['borderStrong', 'color-border-strong'],
  ['textPrimary', 'color-text-primary'],
  ['textSecondary', 'color-text-secondary'],
  ['textTertiary', 'color-text-muted'],
  ['violet', 'color-diagnostic'],
];

// backgroundElevated: web raised in dark; light raised is plain white, so the
// app's chip/track/sheet fill uses web's muted surface there.
const ELEVATED: Record<string, string> = { dark: 'color-surface-raised', light: 'color-surface-muted' };

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

test('neutral ramp keeps WCAG AA text contrast (muted text on every app surface)', () => {
  const lum = (hex: string) => {
    const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
  };
  const ratio = (a: string, b: string) => {
    const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p);
    return (x + 0.05) / (y + 0.05);
  };
  for (const [mode, themeName] of [['dark', 'darkColors'], ['light', 'lightColors']] as const) {
    const block = themeBlock(themeName);
    for (const text of ['textPrimary', 'textSecondary', 'textTertiary']) {
      for (const bg of ['background', 'surface', 'backgroundElevated']) {
        const r = ratio(themeColor(block, text), themeColor(block, bg));
        assert.ok(r >= 4.5, `${mode} ${text} on ${bg} is ${r.toFixed(2)}:1`);
      }
    }
  }
});

test('backgroundElevated and soft fills match web', () => {
  for (const [mode, cssBlock, themeName] of [['dark', darkCss, 'darkColors'], ['light', lightCss, 'lightColors']] as const) {
    const block = themeBlock(themeName);
    assert.equal(themeColor(block, 'backgroundElevated'), cssVar(cssBlock, ELEVATED[mode]), `${mode} backgroundElevated`);
  }
  const lightBlock = themeBlock('lightColors');
  for (const [key, variable] of [['dangerMuted', 'color-danger-soft'], ['successMuted', 'color-success-soft'], ['warningMuted', 'color-warning-soft'], ['accentMuted', 'color-accent-soft']]) {
    assert.equal(themeColor(lightBlock, key), cssVar(lightCss, variable), `light ${key}`);
  }
});

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
