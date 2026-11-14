import React, { useState } from 'react';
import { Pressable, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import Button from './Button';
import { animateRowExpand } from './PlayerAccordionRow';
import { withAlpha } from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import type { SimMoveKind, SimMoveSpec } from '../lib/simMove';
import { radii, spacing } from '../theme';

/** What a screen supplies: run one action (optionally with the chosen slot / taxi player). The strip never calls the API itself. */
export type SimMoveRun = (kind: SimMoveKind, targetKey?: string) => Promise<unknown> | void;

export interface SimMoveHandle {
  specs: SimMoveSpec[];
  run: SimMoveRun;
  /** Why an expected move is missing (roster full, IR full). */
  notes?: string[];
  /** The server's reason when it refused a move; shown under the strip. */
  refusal?: string | null;
}

/**
 * THE one trailing control of a sim roster row: a single Move button. It toggles the row's in-place expansion (the same
 * accordion state as tapping the row). Twin of web SimMoveStrip.tsx.
 */
export function SimMoveButton({ name, open, onToggle }: { name: string; open: boolean; onToggle: () => void }) {
  const { colors } = useThemeMode();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`Move ${name}`}
      accessibilityState={{ expanded: open }}
      testID="move-button"
      onPress={() => {
        animateRowExpand();
        onToggle();
      }}
      style={{
        width: 40,
        height: 40,
        alignItems: 'center',
        justifyContent: 'center',
        borderRadius: radii.md,
        borderWidth: 1,
        borderColor: open ? colors.accent : 'transparent',
        backgroundColor: open ? withAlpha(colors.accent, 0.15) : withAlpha(colors.textTertiary, 0.12),
      }}
    >
      <Ionicons name="ellipsis-horizontal" size={20} color={open ? colors.accent : colors.textSecondary} />
    </Pressable>
  );
}

/**
 * The inline action strip an open roster row shows: only the actions that are possible right now (lib/simMove.ts), one
 * primary. An action with choices reveals chips; Cut asks "Cut Name?" with Cut / Keep first. No sheet.
 */
export function SimMoveStrip({ specs, run, refusal, notes }: SimMoveHandle) {
  const { colors } = useThemeMode();
  const [choosing, setChoosing] = useState<SimMoveKind | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);

  async function go(kind: SimMoveKind, key?: string) {
    if (busy) return;
    setBusy(key ? `${kind}:${key}` : kind);
    try {
      await run(kind, key);
    } finally {
      setBusy(null);
    }
  }

  const cut = specs.find((s) => s.kind === 'cut');
  const picking = specs.find((s) => s.kind === choosing && s.targets);
  if (specs.length === 0) return null;

  return (
    <View style={{ gap: spacing.sm }} testID="move-strip">
      {confirming && cut ? (
        <View style={{ flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: spacing.sm }} testID="move-cut-confirm">
          <AppText style={{ fontSize: 14, fontWeight: '700', color: colors.danger }}>{cut.confirm}</AppText>
          <Button size="sm" variant="danger" label="Cut" loading={busy === 'cut'} onPress={() => void go('cut')} />
          <Button size="sm" variant="ghost" label="Keep" disabled={busy !== null} onPress={() => setConfirming(false)} />
        </View>
      ) : (
        <View style={{ flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: spacing.sm }}>
          {specs.map((spec) => (
            <Button
              key={spec.kind}
              size="sm"
              variant={spec.primary ? 'primary' : spec.danger ? 'dangerOutline' : 'secondary'}
              label={spec.label}
              loading={busy === spec.kind}
              disabled={busy !== null && busy !== spec.kind}
              onPress={() => {
                if (spec.targets) setChoosing((cur) => (cur === spec.kind ? null : spec.kind));
                else if (spec.confirm) setConfirming(true);
                else void go(spec.kind);
              }}
            />
          ))}
        </View>
      )}
      {picking?.targets && !confirming ? (
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }} testID="move-targets" accessibilityLabel={picking.label}>
          {picking.targets.map((t) => (
            <Pressable
              key={t.key}
              accessibilityRole="button"
              accessibilityLabel={t.hint ? `${t.label}, ${t.hint}` : t.label}
              disabled={busy !== null}
              onPress={() => void go(picking.kind, t.key)}
              style={{ minHeight: 44, paddingHorizontal: 10, justifyContent: 'center', borderRadius: radii.md, borderWidth: 1, borderColor: colors.borderStrong ?? colors.border, backgroundColor: withAlpha(colors.textTertiary, 0.12) }}
            >
              <AppText style={{ fontSize: 12, fontWeight: '800', color: colors.textPrimary }}>{t.label}</AppText>
              {t.hint ? <AppText style={{ fontSize: 11, color: colors.textTertiary }}>{t.hint}</AppText> : null}
            </Pressable>
          ))}
        </View>
      ) : null}
      {notes && notes.length > 0 ? <AppText style={{ fontSize: 12, color: colors.textTertiary }} testID="move-notes">{notes.join(' ')}</AppText> : null}
      {refusal ? (
        <AppText style={{ fontSize: 14, fontWeight: '700', color: colors.warning }} accessibilityRole="alert" testID="reserve-refusal">{refusal}</AppText>
      ) : null}
    </View>
  );
}
