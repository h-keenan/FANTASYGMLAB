// Run with: node --experimental-strip-types --test src/lib/simStory.test.ts
import test from 'node:test';
import assert from 'node:assert/strict';

import { compactSummaryText } from './compactModule.ts';
import { injuryCoverageNote, injuryHistoryRows, injurySummaryParts, type InjuryRecordData } from './playerDepthInjury.ts';
import { pqvRealWorld } from './pqvContext.ts';
import { simOutLine, simPlayerStatusLabel, type SimStoryEntry } from './simGame.ts';
import { simStoryGroups, simStorySummaryParts, simStoryToneKey, simStoryWhen } from './simStory.ts';

const line = (e: Partial<SimStoryEntry> & Pick<SimStoryEntry, 'kind' | 'season' | 'week' | 'text'>): SimStoryEntry => ({ year: 2026 + e.season - 1, season_label: `S${e.season} ${2026 + e.season - 1}`, tone: 'neutral', ...e });

const story: SimStoryEntry[] = [
  line({ kind: 'depth', season: 2, week: 0, text: 'Lost the BAL QB1 starting job to R. Cole (rookie won the job)', tone: 'bad' }),
  line({ kind: 'season', season: 1, week: 99, text: 'QB2 · 288.2 pts · 17 games', tone: 'neutral' }),
  line({ kind: 'injury', season: 1, week: 3, text: 'Hamstring in Week 3: out 4 weeks', tone: 'bad', injury: 'Hamstring', weeks: 4 }),
  line({ kind: 'season', season: 2, week: 99, text: 'QB3 · did not play: behind R. Cole, J. Smith', tone: 'bad' }),
];

test('groups by season, newest first, the season line leading', () => {
  const groups = simStoryGroups(story);
  assert.deepEqual(groups.map((g) => g.label), ['S2 2027', 'S1 2026']);
  assert.deepEqual(groups[0].entries.map((e) => e.kind), ['season', 'depth']);
  assert.deepEqual(groups[1].entries.map((e) => e.kind), ['season', 'injury']);
  assert.deepEqual(simStoryGroups(null), []);
});

test('tags a line with its week and tone', () => {
  assert.equal(simStoryWhen({ kind: 'injury', week: 3 }), 'Wk 3');
  assert.equal(simStoryWhen({ kind: 'depth', week: 0 }), 'Offseason');
  assert.equal(simStoryWhen({ kind: 'season', week: 99 }), 'Season');
  assert.deepEqual([simStoryToneKey('good'), simStoryToneKey('bad'), simStoryToneKey('neutral')], ['success', 'danger', 'muted']);
});

test('the collapsed summary leads with his latest season and counts what moved', () => {
  assert.equal(compactSummaryText(simStorySummaryParts(story)), 'QB3 · did not play: behind R. Cole, J. Smith · 1 depth chart move · 1 injury');
  assert.deepEqual(simStorySummaryParts([]), []);
});

test('injury_v names the injury with the weeks out and falls back to the old text without one', () => {
  assert.equal(simOutLine({ out_weeks: 4, injury: 'Hamstring' }), 'Hamstring · out 4 wks');
  assert.equal(simOutLine({ out_weeks: 1, injury: 'Ankle' }), 'Ankle · out 1 wk');
  assert.equal(simOutLine({ out_weeks: 4 }), 'Out 4w');
  assert.equal(simOutLine({ out_weeks: 0 }), 'Out');
  assert.deepEqual(simPlayerStatusLabel({ status: 'out', out_weeks: 9, bye_week: null, injury: 'Torn ACL' }), { label: 'Torn ACL · out 9 wks', tone: 'danger' });
  assert.deepEqual(simPlayerStatusLabel({ status: 'out', out_weeks: 9, bye_week: null }), { label: 'Out 9w', tone: 'danger' });
});

test('the shared injury section reads a sim record: season labels, own coverage note', () => {
  const record: InjuryRecordData = {
    ok: true, current_season: 2027, since_season: 2026, career_games_missed: 7, source: 'sim',
    current: { label: 'Torn ACL', status: 'Out', severity: 'out', unavailable: true, body_part: 'Torn ACL', practice: null, report: 'Out 9 weeks more.', line: 'Torn ACL · out 9 wks' },
    seasons: [
      { season: 2027, season_label: 'S2 2027', games_missed: 4, stints: [{ start_week: 5, end_week: 8, games_missed: 4, injury: 'Hamstring' }] },
      { season: 2026, season_label: 'S1 2026', games_missed: 3, stints: [{ start_week: 3, end_week: 5, games_missed: 3, injury: null }] },
    ],
  };
  assert.deepEqual(injuryHistoryRows(record).map((r) => [r.seasonLabel, r.injury, r.games]), [['S2 2027', 'Hamstring', '4 games'], ['S1 2026', 'Injury (not specified)', '3 games']]);
  assert.equal(compactSummaryText(injurySummaryParts(record)), 'Torn ACL · out 9 wks · 4 games missed in 2027 · 7 career');
  assert.equal(injuryCoverageNote(record), "From this game's own injury log.");
});

test('the sim turns the depth chart and injury sections on but never fetches the real ones', () => {
  const sim = pqvRealWorld(true);
  assert.equal(sim.showDepthChart && sim.showInjuryHistory, true);
  assert.equal(sim.fetchDepthChart || sim.fetchInjuryHistory, false);
  const real = pqvRealWorld(false);
  assert.equal(real.fetchDepthChart && real.fetchInjuryHistory, true);
});
