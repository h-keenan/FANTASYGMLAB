import React from 'react';

import DraftPickAssetRow from './DraftPickAssetRow';
import PlayerIdentityRow from './PlayerIdentityRow';
import ValueStat from './ValueStat';
import type { PresentationAsset } from '../lib/api';
import { injuryShortCode } from '../lib/tradeAssetDisplay';
import { injuryTone } from '../lib/injuryDisplay';

/**
 * The one player-or-pick asset row for a trade package (Dashboard top
 * priority, GM Plan, Portfolio signals). Moved out of DashboardScreen so
 * other screens share it without importing a screen.
 */
export default function TradeAssetRow({
  asset,
  onPressPlayer,
  onPressPick,
}: {
  asset: PresentationAsset;
  /** Player taps (Trade Hub / Finder pass usePlayerQuickView's openPlayer). */
  onPressPlayer?: (asset: PresentationAsset) => void;
  onPressPick?: (asset: PresentationAsset) => void;
}) {
  if (asset.asset_type === 'pick') {
    return (
      <DraftPickAssetRow
        round={asset.round ? Number(asset.round) : null}
        pickNo={asset.pick_no ? Number(asset.pick_no) : null}
        label={asset.label}
        projectedRange={asset.projected_range}
        pickId={asset.pick_id}
        pickTier={asset.pick_tier}
        onPress={onPressPick && asset.pick_id ? () => onPressPick(asset) : undefined}
      />
    );
  }
  return (
    <PlayerIdentityRow
      playerId={asset.player_id}
      name={asset.name ?? 'Unknown'}
      position={asset.position}
      team={asset.team}
      tier={asset.tier}
      overallRating={asset.overall_rating}
      opportunityLabel={asset.role}
      onPress={onPressPlayer && asset.player_id ? () => onPressPlayer(asset) : undefined}
      injuryLabel={asset.injury_status ? injuryShortCode(asset.injury_status) : null}
      injuryTone={injuryTone(asset.injury_status) === 'danger' ? 'risk' : 'watch'}
      trailingExtra={<ValueStat value={asset.score != null ? Math.round(asset.score) : null} />}
    />
  );
}

/** A trade side's assets, order preserved, one shared row per asset. */
export function TradeAssetList({
  assets,
  onPressPlayer,
  onPressPick,
}: {
  assets: PresentationAsset[];
  onPressPlayer?: (asset: PresentationAsset) => void;
  onPressPick?: (asset: PresentationAsset) => void;
}) {
  return (
    <>
      {assets.map((asset, index) => (
        <TradeAssetRow
          key={`${asset.asset_type === 'pick' ? 'pick' : 'player'}-${asset.pick_id ?? asset.player_id ?? index}`}
          asset={asset}
          onPressPlayer={onPressPlayer}
          onPressPick={onPressPick}
        />
      ))}
    </>
  );
}
