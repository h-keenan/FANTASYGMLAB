// Run with: node --experimental-strip-types --test src/lib/multiTeamTrade.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  addTeam,
  analysisLayout,
  analysisOrder,
  buildMatrix,
  buildShareModel,
  buildShareText,
  buildTransfers,
  builderIssue,
  formatSigned,
  isMultiTradeOk,
  lineupEffectText,
  mostHurtBanner,
  multiTradeErrorMessages,
  multiTradeFailureLines,
  removeTeam,
  shareGetsBack,
  toneSemantic,
  upsertAsset,
  vetoTone,
} from './multiTeamTrade.ts';

const asset = (id: string, label: string, position: string, score: number, extra: Record<string, unknown> = {}) => ({
  type: 'player' as const,
  id,
  label,
  position,
  team: 'BUF',
  score,
  ...extra,
});

function team(id: string, name: string, over: Record<string, unknown> = {}) {
  return {
    roster_id: id,
    team_name: name,
    is_perspective: id === '1',
    sends: [],
    receives: [],
    verdict: { ui_verdict: 'FAIR' },
    trade_score: 0,
    market_delta: 0,
    lineup_delta: { per_week: 0 },
    tone: 'fair',
    outcome: 'even',
    why: [],
    veto_risk: null,
    ...over,
  } as never;
}

const teams = (n: number) =>
  Array.from({ length: n }, (_, i) =>
    team(String(i + 1), `Team ${i + 1}`, {
      trade_score: 1000 - i * 400,
      market_delta: 300 - i * 150,
      sends: [asset(`s${i}`, `Sent ${i}`, 'WR', 500, { to_roster_id: String(((i + 1) % n) + 1), to_team_name: `Team ${((i + 1) % n) + 1}` })],
      receives: [asset(`r${i}`, `Got ${i}`, 'RB', 900, { from_roster_id: String(((i + n - 1) % n) + 1), from_team_name: `Team ${((i + n - 1) % n) + 1}` })],
    }),
  );

const response = (n: number) =>
  ({
    status: 'ok',
    teams: teams(n),
    summary: {
      headline: 'h',
      team_count: n,
      balance: { id: 'lopsided', label: 'Lopsided', spread: 1400, best_roster_id: '1', worst_roster_id: String(n) },
      most_hurt_roster_id: String(n),
      best_off_roster_id: '1',
      ranking: [],
    },
  }) as never;

const a = (id: string, from: string, to: string) => ({ type: 'player' as const, id, fromRosterId: from, toRosterId: to });

test('builder needs 3 teams, assets, every team involved', () => {
  assert.equal(builderIssue(['1', '2'], [])?.code, 'too_few_teams');
  assert.equal(builderIssue(['1', '2', '3'], [])?.code, 'no_assets');
  assert.equal(builderIssue(['1', '2', '3'], [a('p', '1', '2')])?.code, 'team_not_involved');
  assert.equal(builderIssue(['1', '2', '3'], [a('p', '1', '2'), a('q', '2', '3')]), null);
});

test('caps at 6 teams, drops a removed team assets, moves an asset once', () => {
  assert.equal(addTeam(['1', '2', '3', '4', '5', '6'], '7').length, 6);
  const out = removeTeam(['1', '2', '3'], [a('p', '1', '2'), a('q', '2', '3'), a('r', '1', '3')], '2');
  assert.deepEqual(out.assets.map((x) => x.id), ['r']);
  const moved = upsertAsset(upsertAsset([], a('p', '1', '2')), a('p', '1', '3'));
  assert.deepEqual(buildTransfers(moved), [{ type: 'player', id: 'p', from_roster_id: '1', to_roster_id: '3' }]);
  assert.equal(buildMatrix(['1', '2', '3'], [a('p', '1', '2')])['1']['2'].length, 1);
});

test('API errors become plain language', () => {
  const [line] = multiTradeErrorMessages([{ code: 'asset_not_owned', message: 'Star QB is not on Team 2' }]);
  assert.match(line, /no longer on the team/);
  assert.match(multiTradeFailureLines({ errors: [{ code: 'too_many_teams' }] })[0], /at most 6/);
  assert.match(multiTradeFailureLines({ reason: 'unsupported_platform' })[0], /Sleeper/);
  assert.deepEqual(multiTradeFailureLines({}), ['Could not analyze this trade.']);
  assert.equal(isMultiTradeOk(response(3)), true);
  assert.equal(isMultiTradeOk({ status: 'invalid' }), false);
});

test('analysis layout, banner and fixed semantic tones', () => {
  assert.equal(analysisLayout(4), 'stack');
  assert.equal(analysisLayout(5), 'ranked');
  assert.deepEqual(analysisOrder(response(3)).map((t) => t.roster_id), ['1', '2', '3']);
  assert.equal(mostHurtBanner(response(3)).headline, 'Most hurt: Team 3');
  assert.equal(formatSigned(1234), '+1,234');
  assert.equal(lineupEffectText({ lineup_delta: { per_week: 2.14, ros: 40 } }), '+2.1 pts a week in the lineup, +40 rest of season');
  assert.equal(toneSemantic('accept'), 'success');
  assert.equal(toneSemantic('decline'), 'danger');
  assert.equal(vetoTone('outrage'), 'danger');
});

test('share model: flow for 3, list for 4+, plain value change, get-back, no scoreboard words', () => {
  assert.equal(buildShareModel(response(3)).layout, 'flow');
  assert.equal(buildShareModel(response(6)).layout, 'list');
  const model = buildShareModel(response(3));
  assert.deepEqual(model.teams.map((t) => t.valueChangeText), ['+300', '+150', '0']);
  const giver = team('2', 'Giver', {
    market_delta: -400,
    receives: [asset('a', 'Starter', 'TE', 800), { type: 'pick', id: 'k', label: '2027 Round 1', position: '', team: '', score: 600 }],
  });
  assert.equal(shareGetsBack(giver), 'Gets back Starter (TE) and 2027 Round 1');
  const text = buildShareText(model, 'My League');
  assert.match(text, /3-team trade in My League/);
  assert.doesNotMatch(text, /most hurt|loses|lopsided|decline/i);
});
