import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Pressable, StyleSheet, TouchableOpacity, useWindowDimensions, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AccentCard from './AccentCard';
import AppText from './AppText';
import Button from './Button';
import DraftPickAssetRow from './DraftPickAssetRow';
import ErrorState from './ErrorState';
import ExchangeSide from './ExchangeSide';
import Input from './Input';
import MultiTeamSharePreviewModal from './MultiTeamSharePreviewModal';
import PickGroupList from './PickGroupList';
import PlayerIdentityRow from './PlayerIdentityRow';
import PremiumLock from './PremiumLock';
import SegmentedTabBar from './SegmentedTabBar';
import SkeletonBlock from './SkeletonBlock';
import { SheetModal, SwipeDismissCard } from './SwipeDismissSheet';
import TeamAvatar from './TeamAvatar';
import ToneBadge from './ToneBadge';
import { api, type DraftPickAsset, type PresentationAsset, type RankedPlayer, type ValuationLens } from '../lib/api';
import { trackUse } from '../lib/analytics';
import { isServerBusyError } from '../lib/busyRetry';
import { mergeSearchMatches, useLeaguePlayerSearch } from '../lib/leaguePlayerSearch';
import {
  MULTI_TEAM_MAX,
  MULTI_TEAM_MIN,
  addTeam,
  analysisLayout,
  analysisOrder,
  buildMatrix,
  buildShareModel,
  buildTransfers,
  builderIssue,
  flowReason,
  formatSigned,
  isMultiTradeOk,
  lineupEffectText,
  mostHurtBanner,
  multiTradeFailureLines,
  orderParticipants,
  removeAsset,
  removeTeam,
  toneSemantic,
  topReasons,
  upsertAsset,
  verdictChipLabel,
  vetoTone,
  type BuilderAsset,
  type MultiAsset,
  type MultiTeamResult,
  type MultiTeamTradeResponse,
  type MultiTransfer,
  type SemanticTone,
} from '../lib/multiTeamTrade';
import { prefillToBuilder } from '../lib/multiTeamIdeas';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, scrim, spacing, type ThemeColors } from '../theme';

/**
 * Multi-team (3 to 6 team) Trade Analyzer, the app twin of web-next's
 * MultiTeamTradeContent. Two separate surfaces: the private, honest ANALYSIS
 * (a card per team, headed by who is most hurt; 5 or 6 teams become a ranked
 * list with tap to expand) and the SHARE picture (persuasion framed, see
 * MultiTeamTradeShareCard). Reads POST .../trade-analyzer/multi; presentation
 * logic is lib/multiTeamTrade.ts, byte-identical to the web file.
 */

const MAX_RESULTS = 40;

export interface MultiPanelTeam {
  rosterId: string;
  name: string;
  avatarId: string | null;
  playerIds: Set<string>;
}

function toPresentation(asset: MultiAsset): PresentationAsset {
  return asset.type === 'pick'
    ? { asset_type: 'pick', label: asset.label, score: asset.score ?? null }
    : {
        asset_type: 'player',
        player_id: asset.id,
        name: asset.label,
        position: asset.position,
        team: asset.team,
        age: asset.age ?? null,
        score: asset.score ?? null,
      };
}

export function multiFailureMessage(error: unknown): string {
  if (isServerBusyError(error)) return 'FantasyDesk is busy right now. Give it a moment and try again.';
  const rate = error as { status?: number; retryAfterSeconds?: number } | null;
  if (rate && rate.status === 429) {
    const wait = rate.retryAfterSeconds ? ` in ${rate.retryAfterSeconds} seconds` : ' in a minute';
    return `You are analyzing a lot of trades at once. Try again${wait}.`;
  }
  if (error instanceof Error && error.message) return error.message;
  return 'Could not analyze this trade.';
}

interface Picker {
  from: string;
  to: string;
}

export default function MultiTeamTradePanel({
  leagueId,
  leagueName,
  myRosterId,
  teams,
  rankings,
  picks,
  lens,
  prefill,
}: {
  leagueId: string;
  leagueName: string;
  myRosterId: string;
  teams: MultiPanelTeam[];
  rankings: RankedPlayer[];
  picks: DraftPickAsset[];
  lens: ValuationLens;
  /** A trade to load and grade on open (a Trade Hub 3-team idea). The Analyzer regrades it: only ids travel. */
  prefill?: MultiTransfer[];
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { width } = useWindowDimensions();
  const wide = width >= 700;

  const toneColor = (tone: SemanticTone) =>
    tone === 'success' ? colors.success : tone === 'warning' ? colors.warning : tone === 'danger' ? colors.danger : colors.textSecondary;

  const [participants, setParticipants] = useState<string[]>(() =>
    prefill?.length ? prefillToBuilder(prefill, myRosterId).participants : myRosterId ? [myRosterId] : [],
  );
  const [assets, setAssets] = useState<BuilderAsset[]>(() =>
    prefill?.length ? (prefillToBuilder(prefill, myRosterId).assets as BuilderAsset[]) : [],
  );
  const [picker, setPicker] = useState<Picker | null>(null);
  const [pending, setPending] = useState<BuilderAsset | null>(null);
  const [addingTeam, setAddingTeam] = useState(false);
  const [search, setSearch] = useState('');
  const [assetType, setAssetType] = useState<'players' | 'picks'>('players');
  const [analyzing, setAnalyzing] = useState(false);
  const [response, setResponse] = useState<MultiTeamTradeResponse | null>(null);
  const [failure, setFailure] = useState<string[] | null>(null);
  const [requestError, setRequestError] = useState<string | null>(null);
  const [shareOpen, setShareOpen] = useState(false);

  const teamById = useMemo(() => new Map(teams.map((t) => [t.rosterId, t])), [teams]);
  const nameOf = (id: string) => teamById.get(id)?.name ?? `Team ${id}`;
  const ordered = orderParticipants(participants, myRosterId);
  const addable = teams.filter((t) => !participants.includes(t.rosterId));

  const searchMatches = useLeaguePlayerSearch(leagueId, lens, picker ? search : '');
  const pool = useMemo(() => mergeSearchMatches(rankings, searchMatches), [rankings, searchMatches]);
  const playerById = useMemo(() => new Map(pool.map((p) => [p.player_id, p])), [pool]);
  const pickById = useMemo(() => new Map(picks.map((p) => [p.pick_id, p])), [picks]);
  const taken = useMemo(() => new Set(assets.map((a) => `${a.type}:${a.id}`)), [assets]);

  const playerResults = useMemo(() => {
    if (!picker) return [];
    const owned = teamById.get(picker.from)?.playerIds ?? new Set<string>();
    const query = search.trim().toLowerCase();
    return pool
      .filter((p) => owned.has(p.player_id) && !taken.has(`player:${p.player_id}`))
      .filter((p) => !query || (p.name ?? '').toLowerCase().includes(query))
      .slice(0, MAX_RESULTS);
  }, [picker, pool, teamById, taken, search]);
  const pickResults = useMemo(() => {
    if (!picker) return [];
    const query = search.trim().toLowerCase();
    return picks
      .filter((p) => p.owner_roster_id === picker.from && !taken.has(`pick:${p.pick_id}`))
      .filter((p) => !query || (p.label ?? '').toLowerCase().includes(query))
      .slice(0, MAX_RESULTS);
  }, [picker, picks, taken, search]);

  const issue = builderIssue(participants, assets);
  const matrix = useMemo(() => buildMatrix(ordered, assets), [ordered, assets]);

  const invalidate = () => {
    setResponse(null);
    setFailure(null);
    setRequestError(null);
  };

  const chooseAsset = (type: 'player' | 'pick', id: string) => {
    if (!picker) return;
    const asset: BuilderAsset = { type, id, fromRosterId: picker.from, toRosterId: picker.to };
    if (picker.to) {
      setAssets((prev) => upsertAsset(prev, asset));
      invalidate();
    } else {
      setPending(asset);
    }
  };

  const chooseDestination = (toRosterId: string) => {
    if (!pending) return;
    setAssets((prev) => upsertAsset(prev, { ...pending, toRosterId }));
    setPending(null);
    invalidate();
  };

  const dropTeam = (rosterId: string) => {
    const next = removeTeam(participants, assets, rosterId);
    setParticipants(next.participants);
    setAssets(next.assets);
    if (picker?.from === rosterId) setPicker(null);
    invalidate();
  };

  const analyze = async () => {
    setFailure(null);
    setRequestError(null);
    setResponse(null);
    setAnalyzing(true);
    try {
      const result = await api.postMultiTeamTradeAnalyzer(leagueId, {
        transfers: buildTransfers(assets),
        perspectiveRosterId: myRosterId,
        lens,
      });
      trackUse('trade_analyzer', 'evaluated', {
        leagueId,
        props: { item_kind: 'multi_team', result: result.status === 'ok' ? 'verdict' : 'no_verdict' },
      });
      if (isMultiTradeOk(result)) setResponse(result);
      else setFailure(multiTradeFailureLines(result));
    } catch (err) {
      setRequestError(multiFailureMessage(err));
    } finally {
      setAnalyzing(false);
    }
  };

  // A prefilled trade is graded once on open, the same request a tap on Analyze makes.
  const autoAnalyzed = useRef(false);
  useEffect(() => {
    if (!prefill?.length || autoAnalyzed.current) return;
    autoAnalyzed.current = true;
    void analyze();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const display = (asset: BuilderAsset): PresentationAsset => {
    if (asset.type === 'pick') {
      const pick = pickById.get(asset.id);
      return { asset_type: 'pick', label: pick?.label ?? asset.id, score: pick?.score ?? null };
    }
    const player = playerById.get(asset.id);
    return { asset_type: 'player', player_id: asset.id, name: player?.name ?? `Player ${asset.id}`, position: player?.position ?? '' };
  };

  const assetName = (asset: BuilderAsset) => display(asset).name ?? display(asset).label ?? asset.id;

  const renderResults = () => {
    if (!isMultiTradeOk(response)) return null;
    const banner = mostHurtBanner(response);
    const order = analysisOrder(response);
    const ranked = analysisLayout(response.teams.length) === 'ranked';
    const vetoLocked = Boolean(response.veto_locked);
    const balanceColor = toneColor(response.summary.balance.id === 'balanced' ? 'success' : response.summary.balance.id === 'tilted' ? 'warning' : 'danger');
    return (
      <View style={styles.results} testID="multi-team-results">
        <AccentCard accent={balanceColor}>
          <AppText style={styles.bannerHeadline} testID="most-hurt-banner">
            {banner.headline}
          </AppText>
          <View style={styles.rowWrap}>
            <ToneBadge label={response.summary.balance.id.toUpperCase()} color={balanceColor} />
            <AppText style={styles.secondary}>{banner.balance}</AppText>
          </View>
          <AppText style={styles.secondary}>{response.summary.headline}</AppText>
          <AppText style={styles.muted}>This private read is for you. It does not use up a free evaluation.</AppText>
        </AccentCard>
        {vetoLocked ? (
          <PremiumLock
            feature="veto_risk"
            title={response.veto_upsell?.title ?? 'See which teams might cry foul'}
            description={response.veto_upsell?.body ?? 'Veto risk for every team is a Pro detail.'}
            leagueName={leagueName}
          />
        ) : null}
        {order.map((team, index) =>
          ranked ? (
            <RankedRow key={team.roster_id} team={team} rank={index + 1} vetoLocked={vetoLocked} toneColor={toneColor} styles={styles} />
          ) : (
            <TeamResultCard key={team.roster_id} team={team} vetoLocked={vetoLocked} toneColor={toneColor} styles={styles} />
          ),
        )}
        <View style={styles.shareBox}>
          <AppText style={styles.sectionTitle}>Pitch it to the other managers</AppText>
          <AppText style={styles.secondary}>
            The picture leads with what every team gets and the needs it fills. It still shows each team&apos;s real value change.
          </AppText>
          <Button label="Share the pitch" onPress={() => setShareOpen(true)} size="sm" />
        </View>
        <MultiTeamSharePreviewModal
          visible={shareOpen}
          onClose={() => setShareOpen(false)}
          leagueId={leagueId}
          leagueName={leagueName}
          model={buildShareModel(response)}
        />
      </View>
    );
  };

  return (
    <View style={styles.root}>
      <AppText style={styles.intro}>
        Build a trade between {MULTI_TEAM_MIN} to {MULTI_TEAM_MAX} teams. Add each team, then pick what every team sends and who receives it.
      </AppText>

      {ordered.map((rosterId) => {
        const sends = assets.filter((a) => a.fromRosterId === rosterId);
        const isMe = rosterId === myRosterId;
        const open = picker?.from === rosterId;
        return (
          <View key={rosterId} style={[styles.teamPanel, open && styles.teamPanelActive]} testID="team-panel">
            <View style={styles.teamHeader}>
              <TeamAvatar avatarId={teamById.get(rosterId)?.avatarId ?? null} size={22} />
              <AppText style={styles.teamName} numberOfLines={1}>
                {nameOf(rosterId)}
                {isMe ? '  YOU' : ''}
              </AppText>
              <Button
                label={open ? 'Done' : 'Add asset'}
                variant="secondary"
                size="sm"
                onPress={() => {
                  setPicker(open ? null : { from: rosterId, to: '' });
                  setSearch('');
                }}
              />
              {!isMe ? <Button label="Remove" variant="ghost" size="sm" onPress={() => dropTeam(rosterId)} /> : null}
            </View>
            {sends.length ? (
              sends.map((asset, index) => (
                <View key={`${asset.type}:${asset.id}`} style={styles.assetLine}>
                  <View style={styles.assetRow}>
                    {asset.type === 'pick' ? (
                      <DraftPickAssetRow
                        pickId={asset.id}
                        round={pickById.get(asset.id)?.round}
                        label={pickById.get(asset.id)?.label}
                        projectedRange={pickById.get(asset.id)?.projected_pick_range}
                        showDivider={index < sends.length - 1}
                      />
                    ) : (
                      <PlayerIdentityRow
                        playerId={asset.id}
                        name={playerById.get(asset.id)?.name}
                        position={playerById.get(asset.id)?.position}
                        team={playerById.get(asset.id)?.team}
                        tier={playerById.get(asset.id)?.tier}
                        overallRating={playerById.get(asset.id)?.overall_rating}
                        showDivider={index < sends.length - 1}
                      />
                    )}
                  </View>
                  <TouchableOpacity accessibilityRole="button" accessibilityLabel="Change who receives this asset" onPress={() => setPending(asset)} hitSlop={6}>
                    <AppText style={[styles.destination, !asset.toRosterId && { color: colors.warning }]} numberOfLines={1}>
                      {asset.toRosterId ? `to ${nameOf(asset.toRosterId)}` : 'Choose team'}
                    </AppText>
                  </TouchableOpacity>
                  <TouchableOpacity
                    accessibilityRole="button"
                    accessibilityLabel={`Remove ${assetName(asset)}`}
                    hitSlop={8}
                    onPress={() => {
                      setAssets((prev) => removeAsset(prev, asset.type, asset.id));
                      invalidate();
                    }}
                  >
                    <Ionicons name="close-circle-outline" size={20} color={colors.textTertiary} />
                  </TouchableOpacity>
                </View>
              ))
            ) : (
              <AppText style={styles.muted}>Sends nothing yet</AppText>
            )}
            {open ? (
              <View style={styles.pickerBox} testID="asset-picker">
                <SegmentedTabBar<'players' | 'picks'>
                  options={[
                    { key: 'players', label: 'Players' },
                    { key: 'picks', label: 'Picks' },
                  ]}
                  active={assetType}
                  onChange={setAssetType}
                />
                <Input
                  placeholder={`Search ${nameOf(rosterId)}'s ${assetType === 'picks' ? 'picks' : 'roster'}`}
                  value={search}
                  onChangeText={setSearch}
                  autoCapitalize="none"
                  accessibilityLabel={`Search ${nameOf(rosterId)}`}
                />
                {assetType === 'picks' ? (
                  pickResults.length ? (
                    <PickGroupList
                      picks={pickResults}
                      renderPick={(pick, isLast) => (
                        <DraftPickAssetRow
                          pickId={pick.pick_id}
                          round={pick.round}
                          label={pick.label}
                          projectedRange={pick.projected_pick_range}
                          pickTier={pick.pick_tier}
                          trailingValue={pick.score != null ? String(Math.round(pick.score)) : '—'}
                          showDivider={!isLast}
                          onPress={() => chooseAsset('pick', pick.pick_id)}
                        />
                      )}
                    />
                  ) : (
                    <AppText style={styles.muted}>{search ? 'No matching picks.' : 'No picks available.'}</AppText>
                  )
                ) : playerResults.length ? (
                  playerResults.map((player, index) => (
                    <PlayerIdentityRow
                      key={player.player_id}
                      playerId={player.player_id}
                      name={player.name}
                      position={player.position}
                      team={player.team}
                      tier={player.tier}
                      overallRating={player.overall_rating}
                      positionRank={player.position_rank}
                      trailingValue={typeof player.score === 'number' ? String(Math.round(player.score)) : '—'}
                      onPress={() => chooseAsset('player', player.player_id)}
                      showDivider={index < playerResults.length - 1}
                    />
                  ))
                ) : (
                  <AppText style={styles.muted}>{search ? 'No matching players.' : 'No players to show.'}</AppText>
                )}
              </View>
            ) : null}
          </View>
        );
      })}

      {participants.length < MULTI_TEAM_MAX ? (
        <View style={styles.addTeamBox}>
          <Button label="Add a team" variant="secondary" onPress={() => setAddingTeam(true)} />
        </View>
      ) : (
        <AppText style={styles.muted}>A trade can include up to {MULTI_TEAM_MAX} teams.</AppText>
      )}

      {wide && participants.length >= MULTI_TEAM_MIN ? (
        <View style={styles.matrix} testID="trade-matrix">
          <AppText style={styles.sectionTitle}>Who sends what to whom</AppText>
          <View style={styles.matrixRow}>
            <View style={styles.matrixHead} />
            {ordered.map((to) => (
              <AppText key={to} style={[styles.matrixHead, styles.matrixHeadText]} numberOfLines={1}>
                {nameOf(to)}
              </AppText>
            ))}
          </View>
          {ordered.map((from) => (
            <View key={from} style={styles.matrixRow}>
              <AppText style={[styles.matrixHead, styles.matrixHeadText]} numberOfLines={1}>
                {nameOf(from)}
              </AppText>
              {ordered.map((to) => {
                const cell = matrix[from]?.[to] ?? [];
                return from === to ? (
                  <View key={to} style={styles.matrixCell}>
                    <AppText style={styles.muted}>-</AppText>
                  </View>
                ) : (
                  <TouchableOpacity
                    key={to}
                    style={styles.matrixCell}
                    accessibilityRole="button"
                    accessibilityLabel={`Add an asset from ${nameOf(from)} to ${nameOf(to)}`}
                    onPress={() => {
                      setPicker({ from, to });
                      setSearch('');
                    }}
                  >
                    <AppText style={[styles.matrixCellText, !cell.length && { color: colors.accent }]} numberOfLines={3}>
                      {cell.length ? cell.map(assetName).join(', ') : '+ Add'}
                    </AppText>
                  </TouchableOpacity>
                );
              })}
            </View>
          ))}
        </View>
      ) : null}

      <Button
        label={analyzing ? 'Analyzing…' : `Analyze ${participants.length}-team trade${assets.length ? ` (${assets.length} assets)` : ''}`}
        onPress={analyze}
        disabled={Boolean(issue)}
        loading={analyzing}
        style={styles.analyze}
      />
      {issue ? <AppText style={styles.muted}>{issue.message}</AppText> : null}

      {analyzing ? (
        <View style={styles.results} testID="multi-team-skeleton" accessibilityLabel="Grading the trade for every team">
          <SkeletonBlock height={72} radius={radii.lg} />
          {Array.from({ length: Math.min(4, Math.max(3, participants.length)) }, (_, i) => (
            <SkeletonBlock key={i} height={120} radius={radii.lg} />
          ))}
        </View>
      ) : null}
      {requestError ? <ErrorState compact title="Couldn't analyze this trade" message={requestError} onRetry={analyze} /> : null}
      {failure ? (
        <View style={styles.failure} testID="multi-team-failure" accessibilityRole="alert">
          {failure.map((line) => (
            <AppText key={line} style={styles.failureText}>
              {line}
            </AppText>
          ))}
        </View>
      ) : null}
      {renderResults()}

      <SheetModal visible={Boolean(pending)} transparent animationType="fade" onRequestClose={() => setPending(null)}>
        <Pressable style={styles.backdrop} onPress={() => setPending(null)}>
          <SwipeDismissCard style={styles.sheet} onDismiss={() => setPending(null)}>
            <AppText style={styles.sheetTitle}>Send to</AppText>
            {ordered
              .filter((id) => id !== pending?.fromRosterId)
              .map((id) => (
                <Button
                  key={id}
                  label={nameOf(id)}
                  variant={pending?.toRosterId === id ? 'primary' : 'secondary'}
                  onPress={() => chooseDestination(id)}
                  style={styles.sheetButton}
                />
              ))}
            <Button label="Cancel" variant="ghost" onPress={() => setPending(null)} />
          </SwipeDismissCard>
        </Pressable>
      </SheetModal>

      <SheetModal visible={addingTeam} transparent animationType="fade" onRequestClose={() => setAddingTeam(false)}>
        <Pressable style={styles.backdrop} onPress={() => setAddingTeam(false)}>
          <SwipeDismissCard style={styles.sheet} onDismiss={() => setAddingTeam(false)}>
            <AppText style={styles.sheetTitle}>Add a team</AppText>
            {addable.map((team) => (
              <Button
                key={team.rosterId}
                label={team.name}
                variant="secondary"
                onPress={() => {
                  setParticipants((prev) => addTeam(prev, team.rosterId));
                  setAddingTeam(false);
                  invalidate();
                }}
                style={styles.sheetButton}
              />
            ))}
            <Button label="Cancel" variant="ghost" onPress={() => setAddingTeam(false)} />
          </SwipeDismissCard>
        </Pressable>
      </SheetModal>
    </View>
  );
}

type Styles = ReturnType<typeof createStyles>;

function TeamResultBody({
  team,
  vetoLocked,
  toneColor,
  styles,
}: {
  team: MultiTeamResult;
  vetoLocked: boolean;
  toneColor: (tone: SemanticTone) => string;
  styles: Styles;
}) {
  const reasons = topReasons(team, 3);
  const veto = team.veto_risk;
  return (
    <>
      <ExchangeSide side="send" label="Sends" assets={team.sends.map(toPresentation)} />
      <ExchangeSide side="get" label="Receives" assets={team.receives.map(toPresentation)} />
      <AppText style={styles.muted}>{flowReason(team)}</AppText>
      {reasons.map((reason) => (
        <AppText key={`${reason.factor}-${reason.text}`} style={styles.reason}>
          {`• ${reason.text}`}
        </AppText>
      ))}
      {veto ? (
        <View style={styles.rowWrap} testID="veto-risk">
          <ToneBadge label={`Veto risk: ${veto.label ?? veto.band ?? ''}`} color={toneColor(vetoTone(veto.band))} />
          {veto.advice ? <AppText style={styles.secondary}>{veto.advice}</AppText> : null}
        </View>
      ) : vetoLocked ? (
        <AppText style={styles.muted}>Veto risk is a Pro detail.</AppText>
      ) : null}
    </>
  );
}

function TeamStats({ team, styles }: { team: MultiTeamResult; styles: Styles }) {
  return (
    <View style={styles.rowWrap}>
      <AppText style={styles.secondary}>
        VALUE <AppText style={styles.strong}>{formatSigned(team.market_delta)}</AppText>
      </AppText>
      <AppText style={styles.secondary}>{lineupEffectText(team)}</AppText>
    </View>
  );
}

function TeamResultCard({
  team,
  vetoLocked,
  toneColor,
  styles,
}: {
  team: MultiTeamResult;
  vetoLocked: boolean;
  toneColor: (tone: SemanticTone) => string;
  styles: Styles;
}) {
  const tone = toneColor(toneSemantic(team.tone));
  return (
    <AccentCard accent={tone}>
      <View style={styles.teamResultHeader}>
        <AppText style={styles.resultName}>
          {team.team_name}
          {team.is_perspective ? '  YOU' : ''}
        </AppText>
        <ToneBadge label={verdictChipLabel(team)} color={tone} />
      </View>
      <TeamStats team={team} styles={styles} />
      <TeamResultBody team={team} vetoLocked={vetoLocked} toneColor={toneColor} styles={styles} />
    </AccentCard>
  );
}

function RankedRow({
  team,
  rank,
  vetoLocked,
  toneColor,
  styles,
}: {
  team: MultiTeamResult;
  rank: number;
  vetoLocked: boolean;
  toneColor: (tone: SemanticTone) => string;
  styles: Styles;
}) {
  const [open, setOpen] = useState(false);
  const tone = toneColor(toneSemantic(team.tone));
  return (
    <AccentCard accent={tone} compact>
      <TouchableOpacity accessibilityRole="button" accessibilityState={{ expanded: open }} onPress={() => setOpen((v) => !v)} style={styles.rankedHead}>
        <AppText style={styles.rank}>{rank}</AppText>
        <AppText style={styles.rankedName} numberOfLines={1}>
          {team.team_name}
          {team.is_perspective ? ' (you)' : ''}
        </AppText>
        <AppText style={styles.strong}>{formatSigned(team.market_delta)}</AppText>
        <ToneBadge label={verdictChipLabel(team)} color={tone} />
      </TouchableOpacity>
      {open ? (
        <View style={styles.expanded}>
          <TeamStats team={team} styles={styles} />
          <TeamResultBody team={team} vetoLocked={vetoLocked} toneColor={toneColor} styles={styles} />
        </View>
      ) : null}
    </AccentCard>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    root: { gap: spacing.sm },
    intro: { fontSize: 13.5, color: colors.textSecondary, lineHeight: 18 },
    teamPanel: {
      gap: spacing.sm,
      padding: spacing.md,
      borderRadius: radii.md,
      borderWidth: 1,
      borderColor: colors.glassBorder,
      backgroundColor: colors.glass,
    },
    teamPanelActive: { borderColor: colors.accent },
    teamHeader: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    teamName: { flex: 1, fontSize: 14, fontWeight: '800', color: colors.textPrimary },
    assetLine: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    assetRow: { flex: 1, minWidth: 0 },
    destination: { fontSize: 12, fontWeight: '700', color: colors.accent, maxWidth: 110 },
    pickerBox: { gap: spacing.sm, paddingTop: spacing.sm },
    addTeamBox: { marginTop: spacing.xs },
    analyze: { marginTop: spacing.sm },
    muted: { fontSize: 12, color: colors.textTertiary },
    secondary: { fontSize: 13, color: colors.textSecondary, lineHeight: 18 },
    strong: { fontSize: 14, fontWeight: '900', color: colors.textPrimary },
    reason: { fontSize: 13, color: colors.textSecondary, lineHeight: 18 },
    rowWrap: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: spacing.sm },
    results: { gap: spacing.md, marginTop: spacing.sm },
    bannerHeadline: { fontSize: 16, fontWeight: '900', color: colors.textPrimary },
    sectionTitle: { fontSize: 14, fontWeight: '800', color: colors.textPrimary },
    shareBox: {
      gap: spacing.sm,
      padding: spacing.md,
      borderRadius: radii.md,
      borderWidth: 1,
      borderColor: colors.glassBorder,
      backgroundColor: colors.glass,
    },
    teamResultHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.sm },
    resultName: { flex: 1, fontSize: 15, fontWeight: '900', color: colors.textPrimary },
    rankedHead: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    rank: { width: 18, fontSize: 13, fontWeight: '900', color: colors.textTertiary },
    rankedName: { flex: 1, fontSize: 14, fontWeight: '800', color: colors.textPrimary },
    expanded: { gap: spacing.sm, paddingTop: spacing.sm },
    failure: { gap: 4, padding: spacing.md, borderRadius: radii.md, borderWidth: 1, borderColor: colors.glassBorder, backgroundColor: colors.glass },
    failureText: { fontSize: 13, color: colors.danger },
    matrix: { gap: 4 },
    matrixRow: { flexDirection: 'row', gap: 4 },
    matrixHead: { flex: 1, minWidth: 0 },
    matrixHeadText: { fontSize: 12, fontWeight: '800', color: colors.textPrimary },
    matrixCell: { flex: 1, minWidth: 0, padding: 4, borderWidth: 1, borderColor: colors.border, borderRadius: radii.sm },
    matrixCellText: { fontSize: 12, color: colors.textPrimary },
    backdrop: { flex: 1, backgroundColor: scrim, justifyContent: 'flex-end' },
    sheet: {
      backgroundColor: colors.backgroundElevated,
      borderTopLeftRadius: radii.lg,
      borderTopRightRadius: radii.lg,
      borderWidth: 1,
      borderColor: colors.cardBorder,
      padding: spacing.lg,
      gap: spacing.sm,
    },
    sheetTitle: { fontSize: 16, fontWeight: '800', color: colors.textPrimary, marginBottom: spacing.xs },
    sheetButton: { width: '100%' },
  });
}
