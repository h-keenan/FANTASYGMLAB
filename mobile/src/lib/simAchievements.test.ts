// Run with: node --experimental-strip-types --test src/lib/simAchievements.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { simAchievementColor, simAchievementDate, simAchievementGroups, simAchievementsParts, simAttachAchievements, simRecapAchievementModel, simTeamTrophies, type SimAchievement } from './simAchievements.ts';

const ach = (over: Partial<SimAchievement> = {}): SimAchievement => ({
  id: 'x:1', key: 'x', scope: 'season', rarity: 'common', tone: 'good', icon: 'check', name: 'X', detail: 'd', unlocked: true,
  season_no: 1, year: 2026, season_label: 'S1 2026', week: 5, at: 105, progress: null, tier: null, player: null, ...over,
});

test('gold is for epic good badges only', () => {
  assert.equal(simAchievementColor(ach({ rarity: 'epic' })), 'var(--color-premium)');
  assert.equal(simAchievementColor(ach({ rarity: 'epic', tone: 'bad' })), 'var(--color-danger)');
  assert.equal(simAchievementColor(ach({ rarity: 'rare' })), 'var(--color-accent)');
  assert.equal(simAchievementColor(ach({ rarity: 'epic', unlocked: false })), 'var(--color-text-muted)');
});

test('dates use the shared season label', () => {
  assert.equal(simAchievementDate(ach({ season_label: 'S3 2028', week: 14 })), 'S3 2028 · Wk 14');
});

test('module groups and collapsed summary', () => {
  const items = [ach({ id: 'a:2', season_no: 2, at: 205 }), ach({ id: 'l', unlocked: false, name: 'Perfect Season', progress: { current: 11, target: 14, text: '11-0, 3 games left' }, at: null, week: null })];
  assert.deepEqual(simAchievementGroups({ items }, 2).map((g) => g.title), ['This season', 'Still to earn']);
  assert.deepEqual(simAchievementsParts({ items }).map((p) => p.text), ['1 unlocked', 'next: Perfect Season (11-0, 3 games left)']);
});

test('winless is sympathetic and a perfect season celebrates', () => {
  const sad = simRecapAchievementModel({ new: [ach({ key: 'winless', tone: 'bad', rarity: 'rare', detail: '0-14: not a single win. The #1 pick is yours.' })], milestones: [] });
  assert.equal(sad?.headline, 'Winless... the #1 pick is yours');
  assert.equal(sad?.celebrate, false);
  const best = simRecapAchievementModel({ new: [ach({ key: 'perfect_season', rarity: 'epic', name: 'Perfect Season' })], milestones: [] });
  assert.equal(best?.celebrate, true);
  assert.equal(best?.tone, 'premium');
});

test('attaches each badge to its own week', () => {
  const out = simAttachAchievements([{ week: 14 }, { week: 15 }], { items: [], new: [ach({ id: 'a', week: 15 })], milestones: [] });
  assert.equal(out[0].achievements, undefined);
  assert.equal(out[1].achievements?.new[0].id, 'a');
});

test('trophies newest first', () => {
  const rows = simTeamTrophies([{ season: 1, year: 2026, wins: 10, losses: 4, ties: 0, champion: true }, { season: 3, year: 2028, wins: 12, losses: 2, ties: 0, champion: true }]);
  assert.deepEqual(rows.map((r) => r.label), ['S3 2028', 'S1 2026']);
});
