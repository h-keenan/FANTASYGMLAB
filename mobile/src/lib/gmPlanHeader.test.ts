import assert from 'node:assert/strict';
import test from 'node:test';

import { countPlanNeeds, planHeaderChips } from './gmPlanHeader.ts';

test('planHeaderChips states posture, window and needs from real fields', () => {
  const chips = planHeaderChips({ stance: 'rebuilding', deadlineWeek: 11, pastDeadline: false, needs: 3 });
  assert.deepEqual(chips.map((c) => [c.key, c.value]), [['posture', 'Rebuild'], ['window', 'Wk 11'], ['needs', '3']]);
});

test('planHeaderChips is honest when nothing is set or the window closed', () => {
  assert.deepEqual(planHeaderChips({ stance: '', deadlineWeek: null, pastDeadline: true, needs: 0 }).map((c) => c.value), ['Not set', 'Closed', '0']);
  assert.equal(planHeaderChips({ stance: 'competing', deadlineWeek: null, pastDeadline: false, needs: 0 })[1].value, 'Open');
});

test('countPlanNeeds counts injured-starter positions and relative weak spots only', () => {
  assert.equal(
    countPlanNeeds([
      { items: [{ injury_need_positions: ['TE', 'RB'] }, { relative_weak_spot: true }, { relative_weak_spot: false }, {}] },
      { items: [{ relative_weak_spot: true }] },
    ]),
    4,
  );
});
