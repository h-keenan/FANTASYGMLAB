import ConfirmInPlace from './ConfirmInPlace';
import React, { useMemo, useState } from 'react';
import { StyleSheet, View } from 'react-native';

import AccentCard from './AccentCard';
import AppText from './AppText';
import Button from './Button';
import ToneBadge from './ToneBadge';
import { AnonymousTeamPair } from './TradeOutcomeHeader';
import type { SharedCommunityTrade } from '../lib/api';
import { assetLabel, gradeTone } from '../lib/sharedTrades';
import { useThemeMode } from '../context/ThemeModeContext';
import { spacing, type ThemeColors } from '../theme';

function formatDate(iso: string | null): string {
  if (!iso) return '';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

/**
 * Opt-in shared trades (mirrors web-next SharedTradesFeed). Renders nothing
 * when the storage is not set up (`available` false).
 */
export default function SharedTradesFeed({
  available,
  trades,
  onDelete,
  onReport,
}: {
  available: boolean;
  trades: SharedCommunityTrade[];
  onDelete: (id: string) => void | boolean | Promise<unknown>;
  onReport: (id: string) => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [reported, setReported] = useState<Set<string>>(new Set());
  if (!available) return null;

  const toneColor = { success: colors.success, danger: colors.danger, accent: colors.accent, neutral: colors.textSecondary };
  const visible = trades.filter((trade) => !reported.has(trade.id));

  return (
    <View style={styles.section}>
      <AppText style={styles.heading}>Shared by users</AppText>
      {visible.length === 0 ? <AppText style={styles.muted}>Nothing shared yet.</AppText> : null}
      {visible.map((trade) => (
        <AccentCard key={trade.id} accent={toneColor[gradeTone(trade.grade)]} compact>
          <View style={styles.headerRow}>
            <AnonymousTeamPair color={toneColor[gradeTone(trade.grade)]} />
            <View style={styles.headerText}>
              <AppText style={styles.name} numberOfLines={1}>
                {trade.display_name}
              </AppText>
              {formatDate(trade.created_at) ? <AppText style={styles.muted}>{formatDate(trade.created_at)}</AppText> : null}
            </View>
            <ToneBadge label={trade.band || trade.grade} color={toneColor[gradeTone(trade.grade)]} />
          </View>
          {trade.why ? <AppText style={styles.why}>{trade.why}</AppText> : null}
          <AppText style={styles.sideLabel}>Sent</AppText>
          {trade.send.map((asset, index) => (
            <AppText key={`s-${index}`} style={styles.asset}>
              {assetLabel(asset)}
            </AppText>
          ))}
          <AppText style={styles.sideLabel}>Received</AppText>
          {trade.receive.map((asset, index) => (
            <AppText key={`r-${index}`} style={styles.asset}>
              {assetLabel(asset)}
            </AppText>
          ))}
          {trade.mine ? (
            <ConfirmInPlace
              variant="row"
              mode="ask"
              label="Delete"
              prompt="Delete this shared trade?"
              confirmLabel="Delete"
              errorText="Could not delete it. Try again."
              onConfirm={async () => {
                const result = await onDelete(trade.id);
                return result === false ? false : undefined;
              }}
            />
          ) : (
            <Button
              label="Report"
              variant="ghost"
              onPress={() => {
                setReported((prev) => new Set(prev).add(trade.id));
                onReport(trade.id);
              }}
            />
          )}
        </AccentCard>
      ))}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    section: { gap: spacing.md, marginTop: spacing.lg },
    heading: { fontSize: 17, fontWeight: '700', color: colors.textPrimary },
    card: { padding: spacing.md, gap: spacing.xs },
    headerRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.sm },
    headerText: { flexShrink: 1, flexGrow: 1 },
    name: { fontSize: 16.5, fontWeight: '700', color: colors.textPrimary },
    muted: { fontSize: 13.5, color: colors.textTertiary },
    why: { fontSize: 14.5, color: colors.textSecondary },
    sideLabel: { fontSize: 12.5, fontWeight: '700', color: colors.textTertiary, marginTop: spacing.xs },
    asset: { fontSize: 14.5, color: colors.textPrimary },
  });
}
