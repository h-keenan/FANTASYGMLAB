import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';

import AdpLine, { AdpCredit } from './AdpLine';
import AnimatedCard from './AnimatedCard';
import AppText from './AppText';
import CompactModule from './CompactModule';
import { useThemeMode } from '../context/ThemeModeContext';
import { deltaText, ROOKIE_BOARD_NO_ADP_NOTE, ROOKIE_BOARD_TITLE, rookieBoardSummaryParts } from '../lib/adpPresentation';
import type { RookieAdpBoard as RookieAdpBoardData } from '../lib/api';
import { spacing, type ThemeColors } from '../theme';

const VERDICT_LABEL: Record<string, string> = { value: 'Value', aligned: 'Aligned', reach: 'Reach' };

/** Draft Center rookie board: our rookie rank vs market rookie ADP (mirrors web-next RookieAdpBoard). */
export default function RookieAdpBoard({ board }: { board: RookieAdpBoardData | undefined }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (!board || board.rows.length === 0) return null;
  const withAdp = board.rows.filter((row) => row.adp != null);
  return (
    <CompactModule id="draft.rookie-adp-board" title={ROOKIE_BOARD_TITLE} persist={false} parts={rookieBoardSummaryParts(board.rows)} testID="rookie-adp-board">
      {withAdp.length === 0 ? <AppText style={styles.credit}>{ROOKIE_BOARD_NO_ADP_NOTE}</AppText> : null}
      <AnimatedCard style={styles.card}>
        {board.rows.map((row, index) => (
          <View key={row.player_id} style={[styles.row, index < board.rows.length - 1 && styles.divider]}>
            <AppText style={styles.name}>
              #{row.our_rank} {row.name} · {row.position} {row.team || 'FA'}
            </AppText>
            {row.adp != null ? (
              <>
                <AdpLine
                  style={styles.muted}
                  note={board.est_sf_note ?? undefined}
                  adp={{ adp: row.adp, adp_label: row.adp_label, adp_est_sf: row.adp_est_sf, adp_est_sf_label: row.adp_est_sf_label }}
                />
                {row.verdict ? (
                  <AppText style={styles.muted}>
                    {VERDICT_LABEL[row.verdict]} {deltaText(row.delta)}
                    {row.read ? ` · ${row.read}` : ''}
                  </AppText>
                ) : null}
              </>
            ) : (
              <AppText style={styles.muted}>No ADP yet</AppText>
            )}
          </View>
        ))}
      </AnimatedCard>
      {board.source ? <AdpCredit asOf={board.source.as_of} style={styles.credit} /> : null}
      {board.est_sf_note ? <AppText style={styles.credit}>Est. SF is modeled, not real ADP. {board.est_sf_note}</AppText> : null}
    </CompactModule>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    card: { padding: spacing.md },
    row: { paddingVertical: spacing.sm, gap: 2 },
    divider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
    name: { fontWeight: '700', color: colors.textPrimary },
    muted: { fontSize: 13, color: colors.textTertiary },
    credit: { fontSize: 12, color: colors.textTertiary, paddingVertical: spacing.xs },
  });
}
