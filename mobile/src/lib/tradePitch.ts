/** Partner-addressed pitch for the Trade Analyzer share card. Mirrors
 * web-next's buildPartnerPitch (lib/shareCard/analyzerShare.ts): every line is
 * a fact computed from the asset values the Analyzer shows; unsupported lines
 * are omitted, and a trade that favors the sender never claims otherwise. */

export interface PitchAsset {
  kind: 'player' | 'pick';
  name?: string | null;
  position?: string | null;
  score?: number | null;
  season?: number | string | null;
  round?: number | string | null;
}

export interface TradePitch {
  headline: string;
  lines: string[];
}

const total = (assets: PitchAsset[]) => assets.reduce((sum, a) => sum + (Number(a.score) || 0), 0);

/** `send` = what the sender gives (what the PARTNER receives). */
export function buildPartnerPitch(send: PitchAsset[], receive: PitchAsset[], partnerName?: string | null): TradePitch {
  const gets = total(send);
  const gives = total(receive);
  const net = gets - gives;
  const larger = Math.max(gets, gives);
  const fair = larger > 0 && Math.abs(net) <= larger * 0.05;
  const lines: string[] = [];

  if (net > 0 && !fair) lines.push(`You gain ${Math.round(net).toLocaleString('en-US')} in value`);
  else if (fair) lines.push('Fair value both ways');

  const best = (assets: PitchAsset[]) => {
    const map = new Map<string, PitchAsset>();
    for (const a of assets) {
      if (a.kind === 'pick' || !a.position) continue;
      const cur = map.get(a.position);
      if (!cur || (Number(a.score) || 0) > (Number(cur.score) || 0)) map.set(a.position, a);
    }
    return map;
  };
  const incoming = best(send);
  const outgoing = best(receive);
  let upgrade: { pos: string; gain: number; name: string } | null = null;
  incoming.forEach((inAsset, pos) => {
    const out = outgoing.get(pos);
    if (!out) return;
    const gain = (Number(inAsset.score) || 0) - (Number(out.score) || 0);
    if (gain > 0 && (!upgrade || gain > upgrade.gain)) upgrade = { pos, gain, name: inAsset.name || '' };
  });
  const up = upgrade as { pos: string; gain: number; name: string } | null;
  if (up && up.name) lines.push(`Upgrade at ${up.pos}: ${up.name}`);

  const picksIn = send.filter((a) => a.kind === 'pick');
  if (picksIn.length === 1) {
    lines.push(`Adds a ${picksIn[0].season ?? ''} Round ${picksIn[0].round ?? ''} pick`.replace(/\s+/g, ' '));
  } else if (picksIn.length > 1) {
    lines.push(`Adds ${picksIn.length} draft picks`);
  }

  const name = (partnerName ?? '').trim();
  const favorsPartner = net >= 0 || fair;
  const headline = name ? (favorsPartner ? `A trade that works for ${name}` : `Trade proposal for ${name}`) : 'Trade proposal';
  return { headline, lines: lines.slice(0, 3) };
}
