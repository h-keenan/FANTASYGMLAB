// Run with: node --experimental-strip-types --test src/lib/playerAnatomy.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { barFractions, fairnessMeter, nextOpenId, nextSheetSnap, orderPlayerSheetTabs, PEEK_FIRST_LINE_PX, peekSheetHeight, peekShowsTabs, playerInitials, playerRowModel } from './playerAnatomy.ts';

const chase = { id: '7564', name: "Ja'Marr Chase", team: 'CIN', age: 25 };

test('initials', () => {
  assert.equal(playerInitials("Ja'Marr Chase"), 'JC');
  assert.equal(playerInitials(''), '?');
});
test('desk shows proj, value and trend; sim never value or overall', () => {
  const d = playerRowModel({ player: chase, mode: 'desk', proj: 19.8, value: 92, trend: 4, bye: 12 });
  assert.deepEqual(d.facts.map((f) => f.key), ['proj', 'value', 'trend']);
  const s = playerRowModel({ player: chase, mode: 'sim', grade: 'A-', adp: 3.4, proj: 312, value: 92, ovr: 88, trend: 3 });
  assert.deepEqual(s.facts.map((f) => f.key), ['grade', 'adp', 'proj']);
  assert.doesNotMatch(JSON.stringify(s), /VALUE|OVR|92|88/);
});
test('one open, fairness, bars, snap, tabs', () => {
  assert.equal(nextOpenId('a', 'b'), 'b');
  assert.equal(nextOpenId('b', 'b'), null);
  assert.equal(fairnessMeter(100, 200, 'sim').label, 'A better deal for you');
  assert.deepEqual(barFractions([10, 5, null]), [1, 0.5, 0]);
  assert.equal(nextSheetSnap('peek', -80), 'full');
  assert.deepEqual(orderPlayerSheetTabs([{ key: 'outlook' }, { key: 'overview' }, { key: 'stats' }]).map((t) => t.key), ['overview', 'stats', 'outlook']);
});

test('peek sheet height is computed from the content and clamped to 40-70% of the screen', () => {
  assert.equal(peekSheetHeight({ anchorBottom: 400, viewportH: 844 }), 400 + PEEK_FIRST_LINE_PX);
  assert.equal(peekSheetHeight({ anchorBottom: 210, viewportH: 844 }), Math.round(844 * 0.4));
  assert.equal(peekSheetHeight({ anchorBottom: 900, viewportH: 640 }), Math.round(640 * 0.7));
  assert.equal(peekSheetHeight({ anchorBottom: 400, viewportH: 844, bottomInset: 34 }), 486);
  assert.equal(peekShowsTabs(210, peekSheetHeight({ anchorBottom: 210, viewportH: 844 })), true);
  assert.equal(peekShowsTabs(300, 250), false);
});
