/**
 * Player share card, same visual system as the trade card: header, photo in
 * its tier ring, name, position/team pills, score ring, league value, usage
 * trend and key stats. Every field comes off the server's own RankedPlayer
 * (GET .../rankings) plus the quick-view usage trend, the same data the
 * Player Profile page renders. A missing field drops its block; nothing is
 * invented.
 */

import type { RankedPlayer, UsageTrend } from "@/lib/api";
import { BRAND_DOMAIN, BRAND_NAME } from "@/lib/brand";
import { formatPlayersPercentile, formatPlayersStatValue } from "@/lib/playersPresentation";
import { resolvePlayerTier } from "@/lib/playerTier";

import {
  ShareAvatar,
  ShareChip,
  ShareFrame,
  ShareOvrRing,
  SharePositionBadge,
  ShareQr,
  type ShareBrandAssets,
  eyebrowStyle,
  formatValue,
  glassStyle,
  initials,
} from "./frame";
import { SHARE_TOKEN_HEX as T, shareRadius, tierHex } from "./tokens";

function Pill({ label, size }: { label: string; size: number }) {
  return (
    <div
      style={{
        display: "flex",
        padding: `${Math.round(size * 0.3)}px ${Math.round(size * 0.6)}px`,
        borderRadius: shareRadius("--radius-sm"),
        backgroundColor: T["--color-surface-primary"],
        border: `1.5px solid ${T["--color-border-strong"]}`,
        fontSize: size,
        fontWeight: 800,
        color: T["--color-text-secondary"],
      }}
    >
      {label}
    </div>
  );
}

function StatCell({ label, value, sub, size }: { label: string; value: string; sub?: string; size: number }) {
  return (
    <div style={{ ...glassStyle(), flexDirection: "column", flexGrow: 1, flexBasis: 0, minWidth: 0, padding: `${Math.round(size * 0.4)}px ${Math.round(size * 0.45)}px`, gap: Math.round(size * 0.14) }}>
      <div style={{ ...eyebrowStyle(T["--color-text-muted"], Math.round(size * 0.3)), whiteSpace: "nowrap" }}>{label}</div>
      <div style={{ display: "flex", fontSize: size, fontWeight: 900, lineHeight: 1.05 }}>{value}</div>
      {sub ? <div style={{ display: "flex", fontSize: Math.round(size * 0.3), fontWeight: 600, color: T["--color-text-muted"] }}>{sub}</div> : null}
    </div>
  );
}

/** Usage trend read, e.g. "+18% usage, weighted last 4 games...". */
export function usageSummary(trend: UsageTrend | null): { headline: string; up: boolean; color: string } | null {
  if (!trend || !Number.isFinite(trend.trend_pct)) return null;
  const pct = Math.abs(Math.round(trend.trend_pct));
  const up = trend.direction === "up";
  return { headline: `${pct}% usage`, up, color: up ? T["--color-success"] : T["--color-danger"] };
}

function UsageBlock({ trend, compact }: { trend: UsageTrend; compact: boolean }) {
  const summary = usageSummary(trend);
  if (!summary) return null;
  return (
    <div style={{ ...glassStyle(), flexDirection: "column", flexGrow: 1, flexBasis: 0, minWidth: 0, padding: compact ? "14px 20px" : "24px 30px", gap: compact ? 6 : 10 }}>
      <div style={eyebrowStyle(T["--color-text-muted"], compact ? 14 : 20)}>Usage trend</div>
      <div style={{ display: "flex", alignItems: "center", gap: compact ? 10 : 16, fontSize: compact ? 34 : 54, fontWeight: 900, lineHeight: 1.05, color: summary.color }}>
        <svg width={compact ? 26 : 40} height={compact ? 26 : 40} viewBox="0 0 24 24">
          <path d={summary.up ? "M12 3 22 21H2Z" : "M12 21 2 3h20Z"} fill={summary.color} />
        </svg>
        <span>{summary.headline}</span>
      </div>
      {trend.detail && !compact ? (
        <div style={{ display: "block", fontSize: 22, fontWeight: 500, lineHeight: 1.25, color: T["--color-text-muted"], lineClamp: 2 }}>{trend.detail}</div>
      ) : null}
      {trend.confidence_label ? (
        <div style={{ display: "flex", fontSize: compact ? 14 : 20, fontWeight: 700, color: T["--color-text-muted"] }}>{`${trend.confidence_label.replace(/ confidence$/i, "")} confidence`}</div>
      ) : null}
    </div>
  );
}

export function PlayerShareCard({
  player,
  brand,
  headshot,
  lens,
  usageTrend = null,
  width,
  height,
}: {
  player: RankedPlayer;
  brand: ShareBrandAssets;
  headshot: string | null;
  lens: string;
  usageTrend?: UsageTrend | null;
  width: number;
  height: number;
}) {
  const compact = height < 900;
  const name = player.name || `Player ${player.player_id}`;
  const tierColor = tierHex(player.tier);
  const value = formatValue(player.score);
  const hasRating = player.overall_rating !== null && player.overall_rating !== undefined;
  const stats = (player.stats ?? []).filter((stat) => Number.isFinite(stat.value)).slice(0, compact ? 3 : 4);
  const cells: { label: string; value: string }[] = [];
  if (value) cells.push({ label: `${lens} value`, value });
  if (player.overall_rank) cells.push({ label: "Overall rank", value: `#${player.overall_rank}` });
  if (player.position_rank) cells.push({ label: "Position rank", value: `${player.position || ""}${player.position_rank}` });
  const usage = usageSummary(usageTrend) ? usageTrend : null;

  const hero = (
    <div style={{ ...glassStyle(), alignItems: "center", padding: compact ? "20px 28px" : "36px 40px", gap: compact ? 26 : 36, flexGrow: 1 }}>
      <ShareAvatar src={headshot} tier={player.tier} size={compact ? 170 : 250} fallbackText={initials(name)} />
      <div style={{ display: "flex", flexDirection: "column", flexGrow: 1, flexShrink: 1, minWidth: 0, gap: compact ? 12 : 18 }}>
        <div style={{ display: "block", fontSize: compact ? 54 : 66, fontWeight: 900, lineHeight: 1.04, lineClamp: 2 }}>{name}</div>
        <div style={{ display: "flex", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
          <SharePositionBadge position={player.position} size={compact ? 24 : 30} />
          <Pill label={player.team || "FA"} size={compact ? 22 : 28} />
          {player.age !== null && player.age !== undefined ? <Pill label={`Age ${Math.round(player.age)}`} size={compact ? 22 : 28} /> : null}
          {player.tier && tierColor ? <ShareChip label={resolvePlayerTier(player.tier).semanticLabel} color={tierColor} size={compact ? 16 : 20} /> : null}
        </div>
        {player.opportunity_label ? (
          <div style={{ display: "flex", fontSize: compact ? 20 : 26, fontWeight: 600, color: T["--color-text-muted"] }}>{player.opportunity_label}</div>
        ) : null}
      </div>
      {hasRating ? (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8 }}>
          <ShareOvrRing rating={player.overall_rating} size={compact ? 120 : 150} />
          <div style={eyebrowStyle(T["--color-text-muted"], compact ? 14 : 18)}>Overall</div>
        </div>
      ) : null}
    </div>
  );

  if (compact) {
    return (
      <ShareFrame brand={brand} kind="Player" width={width} height={height} footer={false}>
        {hero}
        <div style={{ display: "flex", gap: 16, alignItems: "stretch" }}>
          {cells.slice(0, 2).map((cell) => (
            <StatCell key={cell.label} label={cell.label} value={cell.value} size={40} />
          ))}
          {usage ? <UsageBlock trend={usage} compact /> : null}
          <div style={{ ...glassStyle(), flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 6, padding: "12px 18px" }}>
            <ShareQr brand={brand} size={84} />
            <div style={{ display: "flex", fontSize: 16, fontWeight: 800 }}>{BRAND_DOMAIN}</div>
            <div style={{ display: "flex", fontSize: 13, fontWeight: 500, color: T["--color-text-muted"] }}>{`Scan to try ${BRAND_NAME}`}</div>
          </div>
        </div>
      </ShareFrame>
    );
  }

  return (
    <ShareFrame brand={brand} kind="Player" width={width} height={height}>
      {hero}
      {cells.length ? (
        <div style={{ display: "flex", gap: 18 }}>
          {cells.map((cell) => (
            <StatCell key={cell.label} label={cell.label} value={cell.value} size={50} />
          ))}
        </div>
      ) : null}
      {usage ? <div style={{ display: "flex" }}><UsageBlock trend={usage} compact={false} /></div> : null}
      {stats.length ? (
        <div style={{ display: "flex", gap: 18 }}>
          {stats.map((stat) => (
            <StatCell
              key={stat.key}
              label={stat.label}
              value={formatPlayersStatValue(stat)}
              sub={stat.percentile != null ? `${formatPlayersPercentile(stat.percentile)} pct` : undefined}
              size={44}
            />
          ))}
        </div>
      ) : null}
    </ShareFrame>
  );
}
