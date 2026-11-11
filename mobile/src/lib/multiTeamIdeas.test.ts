// Run with: node --experimental-strip-types --test src/lib/multiTeamIdeas.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  decodePrefill,
  encodePrefill,
  ideaAnalyzerQuery,
  ideaAsResponse,
  ideaTeamLines,
  ideasSection,
  lockedTeaserTitle,
  prefillKey,
  prefillToBuilder,
} from './multiTeamIdeas.ts';

const TRANSFERS = [
  { type: 'player' as const, id: '4034', from_roster_id: '1', to_roster_id: '2' },
  { type: 'player' as const, id: '6794', from_roster_id: '2', to_roster_id: '3' },
  { type: 'pick' as const, id: '2027:1:3', from_roster_id: '3', to_roster_id: '1' },
];

const team = (id: string, name: string, over: Record<string, unknown> = {}) => ({
  roster_id: id,
  team_name: name,
  is_perspective: id === '1',
  sends: [{ type: 'player', id: `s${id}`, label: `Sends ${id}`, position: 'RB', team: 'SF' }],
  receives: [{ type: 'player', id: `r${id}`, label: `Gets ${id}`, position: 'WR', team: 'SF' }],
  verdict: { ui_verdict: 'Fair' },
  trade_score: 100,
  market_delta: id === '1' ? 120 : -80,
  lineup_delta: { per_week: 1.2 },
  tone: 'fair',
  outcome: 'even',
  why: [{ factor: 'need', text: `${name} fills a WR need.` }],
  ...over,
});

const IDEA = {
  id: 'm3-abc',
  headline: 'h',
  teams: [team('2', 'Team B'), team('1', 'Team A'), team('3', 'Team C')],
  flows: [],
  partners: [],
  user: { roster_id: '1', trade_score: 100, market_delta: 120, lineup_delta: { per_week: 1.2 }, outcome: 'even' },
  summary: {},
  variant: null,
  analyzer_request: { transfers: TRANSFERS, perspective_roster_id: '1' },
} as never;

test('prefill round trips, including pick ids with colons', () => {
  const encoded = encodePrefill(TRANSFERS);
  assert.equal(encoded, 'player~1~2~4034,player~2~3~6794,pick~3~1~2027:1:3');
  assert.deepEqual(decodePrefill(encoded), TRANSFERS);
});

test('prefill drops malformed, duplicate and self-addressed entries and caps the count', () => {
  const raw = ['player~1~2~a', 'player~1~2~a', 'bad~1~2~b', 'player~1~1~c', 'player~1~~d', 'junk'].join(',');
  assert.deepEqual(decodePrefill(raw), [{ type: 'player', id: 'a', from_roster_id: '1', to_roster_id: '2' }]);
  assert.deepEqual(decodePrefill(null), []);
  assert.equal(decodePrefill(Array.from({ length: 50 }, (_, i) => `player~1~2~p${i}`).join(',')).length, 36);
});

test('builder prefill puts the viewer first and routes every asset', () => {
  const state = prefillToBuilder(TRANSFERS, '3');
  assert.equal(state.participants[0], '3');
  assert.equal(state.assets.length, 3);
  assert.equal(prefillKey(TRANSFERS), prefillKey([...TRANSFERS].reverse()));
  assert.equal(
    ideaAnalyzerQuery('Dynasty Overlords', IDEA),
    'name=Dynasty+Overlords&multi=player~1~2~4034,player~2~3~6794,pick~3~1~2027:1:3',
  );
});

test('the section state separates ideas, a locked count, empty and closed', () => {
  assert.equal(ideasSection({ ideas: [IDEA], idea_count: 1, locked: false }).kind, 'ideas');
  assert.deepEqual(ideasSection({ ideas: [], idea_count: 3, locked: true }), { kind: 'locked', count: 3 });
  assert.equal(ideasSection({ ideas: [], idea_count: 0, locked: false, reason: 'no_fit' }).kind, 'empty');
  assert.equal(ideasSection({ ideas: [], idea_count: 0, locked: false, reason: 'trade_deadline_passed' }).kind, 'closed');
  assert.equal(lockedTeaserTitle(1), '1 three-team deal fits your league');
});

test('card lines list the viewer first with a signed value and the need reason', () => {
  const lines = ideaTeamLines(IDEA);
  assert.deepEqual(lines.map((l) => l.name), ['You', 'Team B', 'Team C']);
  assert.equal(lines[0].valueChange, '+120');
  assert.equal(lines[0].why, 'Team A fills a WR need.');
  assert.equal(ideaAsResponse(IDEA).teams?.length, 3);
});
