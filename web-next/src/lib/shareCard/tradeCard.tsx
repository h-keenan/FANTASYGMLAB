/**
 * Trade idea share card: YOU SEND / YOU GET, per-asset value and OVR, the
 * balance and the value-edge verdict. Every field comes straight off the
 * server's own TradeIdea (GET .../trade-hub), the same object the in-app
 * TradeIdeaCardView renders; nothing here is derived beyond formatting.
 */

import type { TradeAsset, TradeIdea } from "@/lib/api";
import { fairnessBandColor, formatTradeGain, leanBar } from "@/lib/tradeHubPresentation";

import {
  ShareAvatar,
  ShareChip,
  ShareFrame,
  ShareOvrRing,
  SharePositionBadge,
  type ShareBrandAssets,
  eyebrowStyle,
  formatValue,
  glassStyle,
  initials,
} from "./frame";
import { SHARE_TOKEN_HEX as T, resolveTokenColor, shareRadius, withAlpha } from "./tokens";

export interface TradeCardImages {
  /** player_id -> headshot data URI (null when Sleeper has no photo). */
  headshots: Record<string, string | null>;
  partnerAvatar: string | null;
}

/** Rows per side before the rest collapse into "+N more": 4, or 3 when
 * both sides are big, so the text never shrinks past phone-legible. */
export function maxRowsPerSide(send: number, receive: number): number {
  return Math.min(send, 4) + Math.min(receive, 4) > 6 ? 3 : 4;
}

/** Row height in px for the number of rows actually drawn. */
export function rowSizeFor(totalRows: number): number {
  if (totalRows <= 2) return 136;
  if (totalRows <= 3) return 116;
  if (totalRows <= 4) return 96;
  if (totalRows <= 5) return 76;
  return 62;
}

function pickTitle(asset: TradeAsset): string {
  if (asset.label) return asset.label;
  const parts = [asset.season, asset.round ? `Round ${asset.round}` : ""].filter(Boolean);
  return parts.length ? `${parts.join(" ")} pick` : "Draft pick";
}

function AssetRow({ asset, size, headshot }: { asset: TradeAsset; size: number; headshot: string | null }) {
  const isPick = asset.asset_type === "pick";
  const nameSize = Math.round(size * 0.32);
  const metaSize = Math.round(size * 0.22);
  const value = formatValue(asset.score);
  const meta: string[] = [];
  if (isPick) {
    if (asset.projected_range) meta.push(asset.projected_range);
    if (asset.owner_team_name) meta.push(`via ${asset.owner_team_name}`);
  } else {
    meta.push(asset.team || "FA");
    if (asset.age !== null && asset.age !== undefined && Number.isFinite(asset.age)) meta.push(`Age ${Math.round(asset.age)}`);
  }
  return (
    <div style={{ display: "flex", alignItems: "center", gap: Math.round(size * 0.22), height: size }}>
      {isPick ? (
        <div
          style={{
            display: "flex",
            width: size * 0.82,
            height: size * 0.82,
            alignItems: "center",
            justifyContent: "center",
            borderRadius: shareRadius("--radius-sm"),
            border: `2px solid ${withAlpha(T["--color-accent"], 0.5)}`,
            backgroundColor: T["--color-accent-soft"],
            ...eyebrowStyle(T["--color-accent"], Math.round(size * 0.2)),
          }}
        >
          {asset.round ? `R${asset.round}` : "PICK"}
        </div>
      ) : (
        <ShareAvatar src={headshot} tier={asset.tier} size={Math.round(size * 0.82)} fallbackText={initials(asset.name)} />
      )}
      <div style={{ display: "flex", flexDirection: "column", flexGrow: 1, flexShrink: 1, minWidth: 0, gap: Math.round(size * 0.06) }}>
        <div
          style={{
            display: "block",
            fontSize: nameSize,
            fontWeight: 800,
            lineHeight: 1.15,
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
          }}
        >
          {isPick ? pickTitle(asset) : asset.name || "Unknown player"}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12, fontSize: metaSize, fontWeight: 600, color: T["--color-text-muted"] }}>
          {isPick ? null : <SharePositionBadge position={asset.position} size={Math.round(metaSize * 0.9)} />}
          <span>{meta.join(" · ")}</span>
        </div>
      </div>
      {isPick ? null : <ShareOvrRing rating={asset.overall_rating} size={Math.round(size * 0.66)} />}
      {value ? (
        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", minWidth: size * 1.05 }}>
          <div style={{ fontSize: Math.round(size * 0.3), fontWeight: 900, lineHeight: 1 }}>{value}</div>
          <div style={{ ...eyebrowStyle(T["--color-text-muted"], Math.round(size * 0.14)), marginTop: 6 }}>Value</div>
        </div>
      ) : null}
    </div>
  );
}

function SideSection({
  label,
  color,
  total,
  assets,
  size,
  maxRows,
  headshots,
}: {
  label: string;
  color: string;
  total: number;
  assets: TradeAsset[];
  size: number;
  maxRows: number;
  headshots: Record<string, string | null>;
}) {
  const shown = assets.slice(0, maxRows);
  const hidden = assets.length - shown.length;
  return (
    <div style={{ ...glassStyle(), flexDirection: "column", padding: "24px 32px", gap: 10 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <div style={{ display: "flex", width: 16, height: 16, borderRadius: 16, backgroundColor: color }} />
          <div style={eyebrowStyle(color, 24)}>{label}</div>
        </div>
        <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
          <div style={eyebrowStyle(T["--color-text-muted"], 18)}>Total</div>
          <div style={{ fontSize: 30, fontWeight: 900 }}>{formatValue(total) || "0"}</div>
        </div>
      </div>
      {shown.map((asset, index) => (
        <AssetRow
          key={`${asset.player_id || asset.label || "asset"}-${index}`}
          asset={asset}
          size={size}
          headshot={asset.player_id ? headshots[asset.player_id] ?? null : null}
        />
      ))}
      {hidden > 0 ? (
        <div style={{ display: "flex", fontSize: 22, fontWeight: 700, color: T["--color-text-muted"] }}>+{hidden} more</div>
      ) : null}
    </div>
  );
}

/** The lean bar (LeanBarMeter): fill grows from the centre toward the
 * side the value leans to. */
function LeanTrack({ sendScore, receiveScore }: { sendScore: number; receiveScore: number }) {
  const lean = leanBar(sendScore, receiveScore);
  const color = lean.polarity === "pos" ? T["--color-success"] : lean.polarity === "neg" ? T["--color-danger"] : T["--color-text-muted"];
  const widthPct = Math.max(lean.polarity === "even" ? 0 : 2, lean.halfTrackPercent);
  return (
    <div style={{ display: "flex", position: "relative", height: 14, borderRadius: 14, backgroundColor: T["--color-border"], width: "100%" }}>
      <div
        style={{
          display: "flex",
          position: "absolute",
          top: 0,
          height: 14,
          borderRadius: 14,
          backgroundColor: color,
          width: `${widthPct}%`,
          left: lean.polarity === "neg" ? `${50 - widthPct}%` : "50%",
        }}
      />
      <div style={{ display: "flex", position: "absolute", left: "50%", top: -6, width: 3, height: 26, backgroundColor: T["--color-text-secondary"] }} />
    </div>
  );
}

export function TradeShareCard({
  idea,
  brand,
  images,
  lens,
  width,
  height,
}: {
  idea: TradeIdea;
  brand: ShareBrandAssets;
  images: TradeCardImages;
  lens: string;
  width: number;
  height: number;
}) {
  const gain = idea.trade_gain;
  const gainColor = gain > 0 ? T["--color-success"] : gain < 0 ? T["--color-danger"] : T["--color-text-secondary"];
  const band = idea.value_edge_band || "";
  const bandColor = resolveTokenColor(fairnessBandColor(band));
  const send = idea.package.send ?? [];
  const receive = idea.package.receive ?? [];
  const maxRows = maxRowsPerSide(send.length, receive.length);
  const size = rowSizeFor(Math.min(send.length, maxRows) + Math.min(receive.length, maxRows));
  const contextBits = [lens, idea.market_realism_label ? `${idea.market_realism_label} to land` : "", idea.confidence_label ? `${idea.confidence_label} confidence` : ""].filter(Boolean);

  return (
    <ShareFrame brand={brand} kind="Trade idea" width={width} height={height}>
      <div style={{ display: "flex", alignItems: "center", gap: 22 }}>
        <ShareAvatar src={images.partnerAvatar} size={76} fallbackText={initials(idea.partner_team_name)} />
        <div style={{ display: "flex", flexDirection: "column", gap: 6, flexShrink: 1, minWidth: 0 }}>
          <div style={eyebrowStyle(T["--color-text-muted"], 20)}>Trade with</div>
          <div style={{ display: "block", fontSize: 46, fontWeight: 900, lineHeight: 1.05, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
            {idea.partner_team_name}
          </div>
        </div>
      </div>

      <div style={{ ...glassStyle(), flexDirection: "column", padding: "28px 32px", gap: 22 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
            <div style={eyebrowStyle(T["--color-text-muted"], 20)}>Balance for you</div>
            <div style={{ fontSize: 88, fontWeight: 900, lineHeight: 1, color: gainColor }}>{formatTradeGain(gain)}</div>
          </div>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 14 }}>
            {band ? <ShareChip label={band} color={bandColor} size={26} /> : null}
            <div style={{ display: "flex", fontSize: 22, fontWeight: 600, color: T["--color-text-muted"] }}>{contextBits.join(" · ")}</div>
          </div>
        </div>
        <LeanTrack sendScore={idea.send_score} receiveScore={idea.receive_score} />
      </div>

      <SideSection label="You send" color={T["--color-danger"]} total={idea.send_score} assets={send} size={size} maxRows={maxRows} headshots={images.headshots} />
      <SideSection label="You get" color={T["--color-success"]} total={idea.receive_score} assets={receive} size={size} maxRows={maxRows} headshots={images.headshots} />
    </ShareFrame>
  );
}
