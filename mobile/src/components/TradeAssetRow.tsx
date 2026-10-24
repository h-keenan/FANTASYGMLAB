import React from 'react';

import DraftPickAssetRow from './DraftPickAssetRow';
import PlayerIdentityRow from './PlayerIdentityRow';
import ValueStat from './ValueStat';
import type { PresentationAsset } from '../lib/api';

/**
 * The one player-or-pick asset row for a trade package (Dashboard top
 * priority, GM Plan, Portfolio signals). Moved out of DashboardScreen so
 * other screens share it without importing a screen.
 */
export default function TradeAssetRow({ asset }: { asset: PresentationAsset }) {
  if (asset.asset_type === 'pick') {
    return (
      <DraftPickAssetRow
        round={asset.round ? Number(asset.round) : null}
        pickNo={asset.pick_no ? Number(asset.pick_no) : null}
        label={asset.label}
        projectedRange={asset.projected_range}
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
      injuryLabel={asset.injury_status ? injuryShortCode(asset.injury_status) : null}
      injuryTone={asset.injury_status && /^(out|ir|injured reserve|sus)/i.test(asset.injury_status) ? 'risk' : 'watch'}
      trailingExtra={<ValueStat value={asset.score != null ? Math.round(asset.score) : null} />}
    />
  );
}

/** Short injury code for the compact pill (Q, D, O, IR); anything else shows as-is. */
function injuryShortCode(status: string): string {
  const normalized = status.trim().toLowerCase();
  if (normalized.startsWith('quest')) return 'Q';
  if (normalized.startsWith('doubt')) return 'D';
  if (normalized === 'out') return 'O';
  if (normalized === 'ir' || normalized.startsWith('injured')) return 'IR';
  return status;
}
