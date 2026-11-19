import React from 'react';
import { View } from 'react-native';

import AppText from './AppText';
import PlayerAvatar from './PlayerAvatar';
import ShareCardChrome from './ShareCardChrome';
import { colors } from '../theme';
import { wrappedShortName, type WrappedShareModel } from '../lib/wrapped';

export const WRAPPED_SHARE_HEIGHT = 480;

/** The card as an exported share graphic (fixed dark palette, captured offscreen). */
export default function WrappedShareCard({ model, shareRef }: { model: WrappedShareModel; shareRef: React.RefObject<View | null> }) {
  return (
    <View style={{ position: 'absolute', left: -2000, top: 0 }} pointerEvents="none">
      <ShareCardChrome ref={shareRef as React.RefObject<View>} kind="Season Wrapped" height={WRAPPED_SHARE_HEIGHT}>
        <AppText style={{ color: colors.accent, fontSize: 12, fontWeight: '800', letterSpacing: 2, marginTop: 6 }}>{model.eyebrow}</AppText>
        <AppText style={{ color: '#f7f8fa', fontSize: 24, fontWeight: '900', marginTop: 2 }}>{model.title}</AppText>
        {model.players.length ? (
          <View style={{ flexDirection: 'row', gap: 10, marginTop: 10 }}>
            {model.players.slice(0, 2).map((p) => (
              <View key={p.id} style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                <PlayerAvatar playerId={p.headshot_id} name={p.name} position={p.pos} team={p.team} size={32} />
                <AppText style={{ color: '#f7f8fa', fontWeight: '800', fontSize: 13 }}>{wrappedShortName(p.name)}</AppText>
              </View>
            ))}
          </View>
        ) : null}
        <AppText style={{ color: '#f7f8fa', fontSize: model.headline.length > 10 ? 34 : 56, fontWeight: '900', marginTop: 12 }}>
          {model.headline}
          {model.unit ? <AppText style={{ fontSize: 16, color: '#a8adb7' }}> {model.unit}</AppText> : null}
        </AppText>
        {model.chip ? <AppText style={{ color: '#4ADE80', fontWeight: '700', fontSize: 13, marginTop: 4 }}>{model.chip}</AppText> : null}
        {model.rows.slice(0, 4).map((r, i) => (
          <View key={i} style={{ flexDirection: 'row', justifyContent: 'space-between', marginTop: 8 }}>
            <AppText style={{ color: '#a8adb7', fontSize: 12, fontWeight: '700' }}>{r.label}</AppText>
            <AppText style={{ color: '#f7f8fa', fontSize: 13, fontWeight: '800' }}>{r.value}</AppText>
          </View>
        ))}
        <AppText style={{ color: '#a8adb7', fontSize: 12, marginTop: 12 }}>{[model.teamName, model.seasonLabel].filter(Boolean).join(' · ')}</AppText>
      </ShareCardChrome>
    </View>
  );
}
