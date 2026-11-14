import test from 'node:test';
import assert from 'node:assert/strict';
import { BADGES, badgeFromInjury, badgeFromTag, badgeLegend, badgesAriaLabel, contextSuppressed, resolveBadges } from './playerBadges.ts';

test('every badge is a glyph of at most two characters on an existing tone', () => {
  for (const b of Object.values(BADGES)) {
    assert.ok([...b.glyph].length <= 2);
    assert.ok(['success', 'danger', 'warning', 'muted', 'accent', 'action'].includes(b.tone));
    assert.ok(b.label.length > 1);
  }
});

test('sorts by severity, drops duplicates and suppressed kinds, folds the rest into +n', () => {
  const r = resolveBadges([{ kind: 'rookie' }, { kind: 'bench' }, { kind: 'out', detail: '2 wks' }, { kind: 'out' }, { kind: 'fa' }, { kind: 'taxi' }], { suppress: ['fa'], max: 3 });
  assert.deepEqual(r.shown.map((b) => b.kind), ['out', 'taxi', 'rookie']);
  assert.equal(r.overflow, 1);
  assert.equal(badgesAriaLabel(r), 'Out: 2 wks, Taxi squad, Rookie, plus 1 more: Bench');
});

test('suppresses a badge that is true for every row, never a health badge', () => {
  assert.deepEqual(contextSuppressed([['rookie'], ['rookie', 'out'], ['rookie']]), ['rookie']);
  assert.deepEqual(contextSuppressed([['rookie'], ['rookie']]), []);
  assert.deepEqual(contextSuppressed([['rookie'], [], ['rookie']]), []);
  assert.deepEqual(contextSuppressed([['out'], ['out'], ['out']]), []);
});

test('maps legacy tags and injury words, leaving non-status tags as text', () => {
  assert.equal(badgeFromTag({ key: 'rookie', label: 'ROOKIE' })?.kind, 'rookie');
  assert.equal(badgeFromTag({ key: 'owner', label: 'Free agent' })?.kind, 'fa');
  assert.equal(badgeFromTag({ key: 'owner', label: 'Taco Tuesday' }), null);
  assert.equal(badgeFromTag({ key: 'block', label: 'On block' })?.kind, 'block');
  assert.deepEqual(badgeFromTag({ key: 'out', label: 'Out 2w' }), { kind: 'out', detail: '2 wks' });
  assert.equal(badgeFromTag({ key: 'role', label: 'Fill-in' })?.kind, 'fillin');
  assert.equal(badgeFromInjury('Questionable'), 'questionable');
  assert.equal(badgeFromInjury('IR'), 'ir');
  assert.equal(badgeFromInjury(''), null);
});

test('lists the legend in severity order', () => {
  assert.equal(badgeLegend()[0].kind, 'out');
  assert.deepEqual(badgeLegend(['bench', 'rookie']).map((b) => b.kind), ['rookie', 'bench']);
});
