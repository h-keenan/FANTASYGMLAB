import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';

import AccentCard from '../components/AccentCard';
import AppText from '../components/AppText';
import BrandedSpinner from '../components/BrandedSpinner';
import Button from '../components/Button';
import EmptyState from '../components/EmptyState';
import ExchangeSide from '../components/ExchangeSide';
import GridBackground from '../components/GridBackground';
import PremiumLock from '../components/PremiumLock';
import ToneBadge from '../components/ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import { useValuationLens } from '../context/ValuationLensContext';
import { api, type TradeTargetOffer, type TradeTargetResponse } from '../lib/api';
import { trackUse } from '../lib/analytics';
import { toUserErrorMessage } from '../lib/errorMessages';
import { useOrbClearance } from '../lib/orbLayout';
import { offerPrefillFrom } from '../lib/tradeOffer';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'TradeOffer'>;

/**
 * "Build an offer" (web twin: TradeOfferContent.tsx). The user picked a player
 * on ANOTHER team; GET .../trade-target (modules/trade_target_offers.py) built
 * 2-3 packages: what to send, what the other side adds back, how likely they
 * are to say yes, and why in plain English. Each card opens in Make a Trade
 * to tweak and share. Pro, gated the same way as Trade Finder.
 */
export default function TradeOfferScreen({ route, navigation }: Props) {
  const { leagueId, leagueName, playerId } = route.params;
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const headerHeight = useHeaderHeight();
  const orbClearance = useOrbClearance();
  const { lens } = useValuationLens(leagueId);
  const [result, setResult] = useState<TradeTargetResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useScreenHeaderTitle(navigation, 'Build an Offer', leagueName);

  const load = useCallback(() => {
    setResult(null);
    setError(null);
    trackUse('trade_offer_built', 'used');
    api
      .getTradeTargetOffers(leagueId, playerId, lens)
      .then(setResult)
      .catch((err) => setError(toUserErrorMessage(err, 'Could not build an offer.')));
  }, [leagueId, playerId, lens]);

  useEffect(() => {
    load();
  }, [load]);

  const acceptColor = (label: TradeTargetOffer['acceptance']['label']) =>
    label === 'Likely' ? colors.success : label === 'Possible' ? colors.warning : colors.danger;

  const openInAnalyzer = (offer: TradeTargetOffer) => {
    trackUse('trade_offer_opened_in_analyzer', 'used');
    navigation.navigate('Trades', {
      leagueId,
      leagueName,
      initialTab: 'make',
      offerPrefill: offerPrefillFrom(offer),
    });
  };

  if (error) {
    return (
      <View style={[styles.root, { paddingTop: headerHeight + spacing.md }, styles.pad]}>
        <EmptyState icon="alert-circle-outline" title="Could not build an offer." subtitle={error} actionLabel="Try again" onPressAction={load} />
      </View>
    );
  }
  if (!result) return <BrandedSpinner style={[styles.center, { paddingTop: headerHeight }]} />;

  if (result.status === 'locked') {
    return (
      <View style={[styles.root, { paddingTop: headerHeight + spacing.md }, styles.pad]}>
        <PremiumLock
          title={result.upsell?.title ?? 'Build an offer for any player'}
          description={result.upsell?.body ?? 'Pick a player on another team and Pro builds the offer for you.'}
          feature="build_an_offer"
          leagueName={leagueName}
        />
      </View>
    );
  }

  return (
    <View style={styles.root}>
      <GridBackground />
      <ScrollView
        contentContainerStyle={[styles.content, { paddingTop: headerHeight + spacing.md, paddingBottom: orbClearance + spacing.lg }]}
      >
        {result.offers.length > 0 ? (
          <>
            <AppText style={styles.headline}>{result.headline}</AppText>
            {result.offers.map((offer) => (
              <AccentCard key={offer.rank} accent={colors.accent}>
                <View style={styles.titleRow}>
                  <AppText style={styles.offerTitle} numberOfLines={2}>
                    Offer {offer.rank}: {offer.title}
                  </AppText>
                  <ToneBadge label={`${offer.acceptance.label} to accept`} color={acceptColor(offer.acceptance.label)} />
                </View>
                <ExchangeSide side="send" assets={offer.package.send} total={offer.send_value} />
                <ExchangeSide side="get" assets={offer.package.receive} total={offer.receive_value} />
                {offer.why.map((line) => (
                  <AppText key={line} style={styles.why}>
                    {'• '}
                    {line}
                  </AppText>
                ))}
                <AppText style={styles.acceptReason}>{offer.acceptance.reason}</AppText>
                <Button label="Open in Trade Analyzer" onPress={() => openInAnalyzer(offer)} />
              </AccentCard>
            ))}
          </>
        ) : (
          <EmptyState
            icon="swap-horizontal-outline"
            title="No offer to show"
            subtitle={result.headline}
            actionLabel={result.status === 'not_rostered' ? 'Go to Waivers' : result.status === 'error' ? 'Try again' : undefined}
            onPressAction={
              result.status === 'not_rostered'
                ? () => navigation.navigate('Waivers', { leagueId, leagueName, playerId })
                : result.status === 'error'
                  ? load
                  : undefined
            }
          />
        )}
      </ScrollView>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: 'transparent' },
    center: { flex: 1, alignItems: 'center', justifyContent: 'center' },
    pad: { paddingHorizontal: spacing.lg },
    content: { paddingHorizontal: spacing.lg, gap: spacing.md },
    headline: { fontSize: 14, color: colors.textSecondary },
    titleRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.sm },
    offerTitle: { flex: 1, fontSize: 15, fontWeight: '700', color: colors.textPrimary },
    why: { fontSize: 13, lineHeight: 19, color: colors.textSecondary },
    acceptReason: { fontSize: 12, color: colors.textTertiary },
  });
}
