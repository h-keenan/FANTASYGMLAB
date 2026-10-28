/**
 * Value-only quick compare of two sides (Side A vs Side B). The band ladder is
 * the shared one (tradeValueBands.generated.ts, generated from
 * modules/trade_value_bands.py) so this value calculator can never draw its
 * lines in a different place than the verdict; only the wording here is
 * Side A/B instead of "you/them". It is a value calculator, not the full
 * accept/decline/counter verdict engine, and is labeled as such in the UI.
 */

import { bandForScore, TRADE_VALUE_BANDS } from './tradeValueBands.generated.ts';

/** Side B is the positive side of the delta. Keyed by shared band id. */
export const SIDE_DIRECTION_LABELS: Record<string, string> = {
  smash: 'Side B wins big on value',
  accept: 'Side B wins on value',
  edge_you: 'Slight value edge to Side B',
  even: 'Value is essentially even',
  edge_them: 'Slight value edge to Side A',
  counter: 'Value edge to Side A',
  decline: 'Large value gap favoring Side A',
  hard: 'Very large value gap favoring Side A',
};

export function valueDirectionLabel(valueDelta: number): string {
  return SIDE_DIRECTION_LABELS[bandForScore(valueDelta).id];
}

export function sideLabelsCoverEveryBand(): boolean {
  return TRADE_VALUE_BANDS.every((band) => typeof SIDE_DIRECTION_LABELS[band.id] === 'string');
}
