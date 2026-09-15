/**
 * Value-only trade delta labeling — ports the raw-value bands from
 * modules/trade_offer_analyzer.py's `_value_direction_label` (same
 * thresholds), but stops there. The web app's full verdict also weighs
 * roster fit, strategy, and injury risk (computed inline in app.py, not yet
 * an importable module), so this is a value calculator, not the full
 * accept/decline/counter verdict engine — labeled as such in the UI.
 */

const VALUE_ACCEPT = 500;
const VALUE_DECLINE = -1200;

export function valueDirectionLabel(valueDelta: number): string {
  if (valueDelta >= VALUE_ACCEPT) return 'Side B wins on asset value';
  if (valueDelta > 150) return 'Slight value edge to Side B';
  if (valueDelta >= -150) return 'Value is essentially even';
  if (valueDelta > VALUE_DECLINE) return 'Slight value edge to Side A';
  return 'Large value gap favoring Side A';
}
