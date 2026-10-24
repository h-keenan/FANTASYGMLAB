import React, { useEffect, useMemo, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AnimatedCard from './AnimatedCard';
import AppText from './AppText';
import Button from './Button';
import DraftPickAssetRow from './DraftPickAssetRow';
import ErrorState from './ErrorState';
import PlayerIdentityRow from './PlayerIdentityRow';
import SectionHeading from './SectionHeading';
import { useThemeMode } from '../context/ThemeModeContext';
import {
  api,
  type LiveDraftPickOption,
  type LiveDraftPickRow,
  type LiveDraftTradeAsset,
  type ValuationLens,
} from '../lib/api';
import { toUserErrorMessage } from '../lib/errorMessages';
import {
  fairnessBandTone,
  formatTradeGain,
  liveDraftDraftedPlayerOptions,
  toggleKey,
} from '../lib/liveDraft';
import { spacing, type ThemeColors } from '../theme';

/**
 * Hypothetical mid-draft Trade Evaluator (port of web-next's
 * LiveDraftTradeEvaluator): pick a send/receive package of not-yet-made
 * picks and already-drafted players, get the server's Favorable / Fair /
 * Slight Overpay / Major Overpay verdict. Nothing is sent to Sleeper.
 */

function CheckList({
  label,
  options,
  selected,
  onToggle,
  emptyLabel,
  colors,
  styles,
}: {
  label: string;
  options: { key: string; label: string }[];
  selected: Set<string>;
  onToggle: (key: string) => void;
  emptyLabel: string;
  colors: ThemeColors;
  styles: ReturnType<typeof createStyles>;
}) {
  return (
    <View style={styles.checkGroup}>
      <AppText style={styles.checkLabel}>{label}</AppText>
      {options.length === 0 ? (
        <AppText style={styles.muted}>{emptyLabel}</AppText>
      ) : (
        <View style={styles.checkBox}>
          {options.map((option, index) => {
            const checked = selected.has(option.key);
            return (
              <Pressable
                key={option.key}
                accessibilityRole="checkbox"
                accessibilityState={{ checked }}
                onPress={() => onToggle(option.key)}
                style={[styles.checkRow, checked && styles.checkRowOn, index < options.length - 1 && styles.checkDivider]}
              >
                <Ionicons
                  name={checked ? 'checkbox' : 'square-outline'}
                  size={20}
                  color={checked ? colors.accent : colors.textTertiary}
                />
                <AppText style={[styles.checkText, checked && { color: colors.accentOnTint }]} numberOfLines={2}>
                  {option.label}
                </AppText>
              </Pressable>
            );
          })}
        </View>
      )}
    </View>
  );
}

function AssetList({ assets, styles }: { assets: LiveDraftTradeAsset[]; styles: ReturnType<typeof createStyles> }) {
  return (
    <View>
      {assets.map((asset, index) => {
        const last = index === assets.length - 1;
        const value = asset.score != null ? String(Math.round(asset.score)) : null;
        return asset.asset_type === 'pick' ? (
          <DraftPickAssetRow
            key={`pick-${index}-${asset.label}`}
            round={asset.round ? Number(asset.round) : null}
            label={asset.label ?? asset.name}
            contextLine={asset.owner_team_name}
            trailingValue={value}
            showDivider={!last}
          />
        ) : (
          <PlayerIdentityRow
            key={`player-${asset.player_id ?? index}`}
            playerId={asset.player_id}
            name={asset.name}
            position={asset.position}
            team={asset.team}
            tier={asset.tier}
            injuryLabel={asset.injury_status}
            trailingValue={value}
            showDivider={!last}
          />
        );
      })}
      {assets.length === 0 ? <AppText style={styles.muted}>Nothing</AppText> : null}
    </View>
  );
}

interface EvaluatorResult {
  send: LiveDraftTradeAsset[];
  receive: LiveDraftTradeAsset[];
  delta: number;
  verdict: string;
}

export default function LiveDraftTradeEvaluator({
  leagueId,
  draftId,
  draftedRows,
  lens,
}: {
  leagueId: string;
  draftId: string;
  draftedRows: LiveDraftPickRow[];
  lens: ValuationLens;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [open, setOpen] = useState(false);
  const [pickOptions, setPickOptions] = useState<LiveDraftPickOption[]>([]);
  const [optionsError, setOptionsError] = useState<string | null>(null);
  const [loadedFor, setLoadedFor] = useState<string | null>(null);
  const [reloadTick, setReloadTick] = useState(0);

  const [sendPicks, setSendPicks] = useState<Set<string>>(new Set());
  const [receivePicks, setReceivePicks] = useState<Set<string>>(new Set());
  const [sendPlayers, setSendPlayers] = useState<Set<string>>(new Set());
  const [receivePlayers, setReceivePlayers] = useState<Set<string>>(new Set());

  const [evaluating, setEvaluating] = useState(false);
  const [result, setResult] = useState<EvaluatorResult | null>(null);
  const [evalError, setEvalError] = useState<string | null>(null);
  const [staleKeys, setStaleKeys] = useState<string[]>([]);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    api
      .getLiveDraftTradeEvaluatorOptions(leagueId, draftId)
      .then((response) => {
        if (cancelled) return;
        setPickOptions(response.pick_options);
        setOptionsError(null);
        setLoadedFor(draftId);
      })
      .catch((err) => {
        if (cancelled) return;
        setOptionsError(toUserErrorMessage(err, 'Could not load the remaining picks.'));
        setLoadedFor(draftId);
      });
    return () => {
      cancelled = true;
    };
  }, [open, leagueId, draftId, reloadTick]);

  const loadingOptions = open && loadedFor !== draftId;
  const playerOptions = useMemo(() => liveDraftDraftedPlayerOptions(draftedRows), [draftedRows]);
  const pickCheckOptions = useMemo(
    () => pickOptions.map((option) => ({ key: option.pick_key, label: option.label })),
    [pickOptions],
  );
  const pickLabelByKey = useMemo(() => {
    const map: Record<string, string> = {};
    for (const option of pickOptions) map[option.pick_key] = option.label;
    return map;
  }, [pickOptions]);

  const clearVerdict = () => {
    setResult(null);
    setEvalError(null);
    setStaleKeys([]);
  };

  const overlap =
    [...sendPicks].some((key) => receivePicks.has(key)) || [...sendPlayers].some((id) => receivePlayers.has(id));
  const canEvaluate =
    (sendPicks.size > 0 || sendPlayers.size > 0) && (receivePicks.size > 0 || receivePlayers.size > 0) && !overlap;

  async function evaluate() {
    setEvaluating(true);
    clearVerdict();
    try {
      const response = await api.postLiveDraftTradeEvaluator(leagueId, draftId, {
        sendPickKeys: [...sendPicks],
        receivePickKeys: [...receivePicks],
        sendPlayerIds: [...sendPlayers],
        receivePlayerIds: [...receivePlayers],
        lens,
      });
      if (response.reason === 'stale_picks') {
        setStaleKeys(response.stale_pick_keys);
      } else if (response.reason === 'assets_not_found') {
        setEvalError('One of the selected assets could not be resolved. Remove it and try again.');
      } else if (response.reason === 'no_player_data') {
        setEvalError("Player data isn't available right now. Try again in a bit.");
      } else {
        setResult({
          send: response.send_assets ?? [],
          receive: response.receive_assets ?? [],
          delta: response.delta ?? 0,
          verdict: response.verdict ?? 'Fair',
        });
      }
    } catch (err) {
      setEvalError(toUserErrorMessage(err, 'Could not evaluate this trade.'));
    } finally {
      setEvaluating(false);
    }
  }

  const tone = result ? fairnessBandTone(result.verdict) : 'neutral';
  const toneColor =
    tone === 'success'
      ? colors.success
      : tone === 'warning'
        ? colors.premium
        : tone === 'danger'
          ? colors.danger
          : colors.textSecondary;

  const sides: Array<{
    title: string;
    color: string;
    picks: Set<string>;
    players: Set<string>;
    setPicks: React.Dispatch<React.SetStateAction<Set<string>>>;
    setPlayers: React.Dispatch<React.SetStateAction<Set<string>>>;
  }> = [
    { title: 'You send', color: colors.danger, picks: sendPicks, players: sendPlayers, setPicks: setSendPicks, setPlayers: setSendPlayers },
    { title: 'You receive', color: colors.success, picks: receivePicks, players: receivePlayers, setPicks: setReceivePicks, setPlayers: setReceivePlayers },
  ];

  return (
    <View>
      <SectionHeading
        title="Trade Evaluator"
        icon="swap-horizontal-outline"
        caption="Hypothetical only. Nothing is sent to Sleeper."
      />
      <AnimatedCard style={styles.card}>
        <Button
          label={open ? 'Hide' : 'Evaluate a trade'}
          variant={open ? 'secondary' : 'primary'}
          onPress={() => setOpen((value) => !value)}
        />
        {open ? (
          loadingOptions ? (
            <AppText style={styles.muted}>Loading remaining picks...</AppText>
          ) : optionsError ? (
            <ErrorState
              compact
              title="Couldn't load picks"
              message={optionsError}
              onRetry={() => {
                setLoadedFor(null);
                setReloadTick((n) => n + 1);
              }}
            />
          ) : (
            <>
              {sides.map((side) => (
                <View key={side.title} style={styles.side}>
                  <AppText style={[styles.sideTitle, { color: side.color }]}>{side.title}</AppText>
                  <CheckList
                    label="Remaining picks"
                    options={pickCheckOptions}
                    selected={side.picks}
                    onToggle={(key) => {
                      side.setPicks((prev) => toggleKey(prev, key));
                      clearVerdict();
                    }}
                    emptyLabel="No remaining picks are open."
                    colors={colors}
                    styles={styles}
                  />
                  <CheckList
                    label="Drafted players"
                    options={playerOptions}
                    selected={side.players}
                    onToggle={(id) => {
                      side.setPlayers((prev) => toggleKey(prev, id));
                      clearVerdict();
                    }}
                    emptyLabel="No players have been drafted yet."
                    colors={colors}
                    styles={styles}
                  />
                </View>
              ))}

              {overlap ? (
                <AppText style={styles.error} accessibilityRole="alert">
                  The same pick or player can't be on both sides of a trade.
                </AppText>
              ) : null}

              <Button label="Evaluate Trade" onPress={evaluate} disabled={!canEvaluate} loading={evaluating} />

              {staleKeys.length > 0 ? (
                <AppText style={styles.error} accessibilityRole="alert">
                  These picks were just selected and can no longer be evaluated:{' '}
                  {staleKeys.map((key) => pickLabelByKey[key] ?? key).join(', ')}. Refresh the selections above and
                  re-submit.
                </AppText>
              ) : null}
              {evalError ? (
                <AppText style={styles.error} accessibilityRole="alert">
                  {evalError}
                </AppText>
              ) : null}

              {result ? (
                <View style={styles.resultBox}>
                  <AppText style={[styles.sideTitle, { color: colors.danger }]}>You send</AppText>
                  <AssetList assets={result.send} styles={styles} />
                  <AppText style={[styles.sideTitle, { color: colors.success, marginTop: spacing.md }]}>
                    You receive
                  </AppText>
                  <AssetList assets={result.receive} styles={styles} />
                  <View style={styles.verdictRow}>
                    <AppText style={styles.checkLabel}>Trade value</AppText>
                    <AppText style={[styles.verdictValue, { color: toneColor }]}>{formatTradeGain(result.delta)}</AppText>
                    <View style={[styles.verdictPill, { borderColor: toneColor }]}>
                      <AppText style={[styles.verdictPillText, { color: toneColor }]}>{result.verdict}</AppText>
                    </View>
                  </View>
                </View>
              ) : null}
            </>
          )
        ) : null}
      </AnimatedCard>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    card: { padding: spacing.md, gap: spacing.md },
    side: { gap: spacing.sm },
    sideTitle: { fontSize: 12, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.5 },
    checkGroup: { gap: spacing.xs },
    checkLabel: { fontSize: 11.5, fontWeight: '700', color: colors.textTertiary, textTransform: 'uppercase', letterSpacing: 0.5 },
    checkBox: { borderWidth: 1, borderColor: colors.border, borderRadius: 10, overflow: 'hidden' },
    checkRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, minHeight: 44, paddingHorizontal: spacing.sm, paddingVertical: spacing.xs },
    checkRowOn: { backgroundColor: colors.accentMuted },
    checkDivider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
    checkText: { flex: 1, fontSize: 13, color: colors.textSecondary, fontWeight: '600' },
    muted: { fontSize: 13, color: colors.textTertiary },
    error: { fontSize: 13, color: colors.danger },
    resultBox: { gap: spacing.xs, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border, paddingTop: spacing.md },
    verdictRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginTop: spacing.md, flexWrap: 'wrap' },
    verdictValue: { fontSize: 24, fontWeight: '800' },
    verdictPill: { borderWidth: 1, borderRadius: 999, paddingHorizontal: spacing.sm, paddingVertical: 2 },
    verdictPillText: { fontSize: 11, fontWeight: '800', textTransform: 'uppercase', letterSpacing: 0.4 },
  });
}
