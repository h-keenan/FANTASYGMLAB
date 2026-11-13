/**
 * Trade idea share card, laid out like the in-app Trade Hub card: a
 * "YOU SEND" (red-tinted) and "YOU GET" (green-tinted) column of player rows
 * (position badge, ringed avatar, rating ring, value), the Balance line with
 * the verdict chip and confidence meter, the server's own rationale, and the QR footer. Every field comes
 * straight off the server's TradeIdea (GET .../trade-hub), the same object
 * the in-app TradeIdeaCardView renders; nothing here is derived beyond
 * formatting. No NFL marks: team identity is the manager's own Sleeper
 * avatar (which the app already shows) or initials.
 *
 * Two sizes: 1080x1350 (stories/posts) and 1200x630 (link unfurls).
 */

import { fitPlayerName } from "@/lib/playerNameDisplay";
import type { TradeAsset, TradeIdea } from "@/lib/api";
import { LOW_CONFIDENCE_USER_NOTE, fairnessBandColor, formatTradeGain } from "@/lib/tradeHubPresentation";

import {
  ShareAvatar,
  ShareFrame,
  ShareChip,
  ShareOvrRing,
  SharePositionBadge,
  ShareQr,
  type ShareBrandAssets,
  eyebrowStyle,
  formatValue,
  glassStyle,
  initials,
} from "./frame";
import { TRADE_SHARE_COPY, plainTradeWhy } from "./tradeCopy";
import { SHARE_TOKEN_HEX as T, resolveTokenColor, shareRadius, withAlpha } from "./tokens";
import { BRAND_DOMAIN, BRAND_NAME } from "@/lib/brand";

export interface TradeCardImages {
  /** player_id -> headshot data URI (null when Sleeper has no photo). */
  headshots: Record<string, string | null>;
  partnerAvatar: string | null;
  myAvatar?: string | null;
}

/** Rows per panel: 4 on the story card, 2 on the short OG card. */
export function maxRowsFor(compact: boolean): number {
  return compact ? 2 : 4;
}

export function pickTitle(asset: TradeAsset): string {
  // Labels can carry the original owner in parentheses; the "via" line
  // already says that, so the title is just the season and round.
  const parts = [asset.season, asset.round ? `Round ${asset.round}` : ""].filter(Boolean);
  if (parts.length) return parts.join(" ");
  return (asset.label || "").replace(/\s*\([^)]*\)\s*$/, "") || "Draft pick";
}

/** Confidence label -> 1..3 meter bars; null when the label isn't one the
 * meter can honestly draw. */
export function confidenceBars(label: string | null | undefined): 1 | 2 | 3 | null {
  const text = (label || "").toLowerCase();
  if (text.startsWith("high")) return 3;
  if (text.startsWith("med") || text.startsWith("mod")) return 2;
  if (text.startsWith("low")) return 1;
  return null;
}

function PickPlate({ asset, size }: { asset: TradeAsset; size: number }) {
  // Same plate as the in-app pick tile: accent-soft square, round label.
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        width: size,
        height: size,
        alignItems: "center",
        justifyContent: "center",
        borderRadius: shareRadius("--radius-sm"),
        border: `2px solid ${withAlpha(T["--color-accent"], 0.5)}`,
        backgroundColor: T["--color-accent-soft"],
        gap: 2,
      }}
    >
      <div style={eyebrowStyle(T["--color-accent"], Math.round(size * 0.3))}>{asset.round ? `R${asset.round}` : "PICK"}</div>
      {asset.season ? <div style={{ display: "flex", fontSize: Math.round(size * 0.18), fontWeight: 700, color: T["--color-text-muted"] }}>{asset.season}</div> : null}
    </div>
  );
}

/** Row tint by side, the app's ExchangeSide colors: red for what you send,
 * green for what you get (danger/success soft tokens, same as the in-app card). */
type Side = "send" | "get";
const SIDE_COLOR: Record<Side, string> = { send: T["--color-danger"], get: T["--color-success"] };
const SIDE_TINT: Record<Side, string> = { send: T["--color-danger-soft"], get: T["--color-success-soft"] };

function AssetRow({ asset, side, size, headshot, compact, tall }: { asset: TradeAsset; side: Side; size: number; headshot: string | null; compact: boolean; tall: boolean }) {
  const isPick = asset.asset_type === "pick";
  const nameSize = tall ? 40 : compact ? Math.round(size * 0.3) : size >= 180 ? 36 : size >= 130 ? 31 : 25;
  const metaSize = tall ? 26 : compact ? Math.round(size * 0.24) : size >= 130 ? 22 : 18;
  const value = formatValue(asset.score);
  const meta: string[] = [];
  if (isPick) {
    meta.push("Draft pick");
    if (asset.owner_team_name && asset.owner_team_name.length <= 10) meta.push(`via ${asset.owner_team_name}`);
  } else {
    meta.push(asset.team || "FA");
    if (asset.age) meta.push(`Age ${asset.age}`);
  }
  const avatar = tall ? 150 : compact ? Math.round(size * 0.7) : Math.min(size >= 180 ? 112 : 92, Math.round(size * 0.55));
  // The compact (link-unfurl) row is single-line with an ellipsis backstop and
  // satori cannot measure text, so estimate how many characters fit (~0.58em
  // per bold glyph in ~380px) and show "F. Lastname" past that instead.
  const fullName = isPick ? pickTitle(asset) : asset.name || "Unknown player";
  const nameText = !isPick && compact ? fitPlayerName(fullName, Math.floor(380 / (nameSize * 0.58))) : fullName;
  const ringSize = tall ? 84 : compact ? Math.round(size * 0.5) : size >= 130 ? 68 : size >= 112 ? 56 : 46;
  const frame = {
    display: "flex",
    flexGrow: 1,
    minHeight: size,
    borderRadius: shareRadius("--radius-md"),
    backgroundColor: SIDE_TINT[side],
    border: `1.5px solid ${withAlpha(SIDE_COLOR[side], 0.35)}`,
  } as const;
  const lead = isPick ? <PickPlate asset={asset} size={avatar} /> : <ShareAvatar src={headshot} tier={asset.tier} size={avatar} fallbackText={initials(asset.name)} />;
  const badge = isPick ? null : <SharePositionBadge position={asset.position} size={Math.round(metaSize * 0.85)} />;
  if (tall) {
    // One player on a side: a centered portrait card that fills the column.
    return (
      <div style={{ ...frame, flexDirection: "column", alignItems: "center", justifyContent: "space-between", padding: "26px 18px" }}>
        {lead}
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12, minWidth: 0, maxWidth: "100%" }}>
          <div style={{ display: "block", fontSize: nameSize, fontWeight: 800, lineHeight: 1.1, textAlign: "center", lineClamp: 2 }}>{nameText}</div>
          <div style={{ display: "flex", alignItems: "center", gap: 12, fontSize: metaSize, fontWeight: 600, color: T["--color-text-muted"] }}>
            {badge}
            <span style={{ display: "block", whiteSpace: "nowrap" }}>{meta.join(" \u00b7 ")}</span>
          </div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
          {isPick ? null : <ShareOvrRing rating={asset.overall_rating} size={ringSize} />}
          {value ? (
            <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start" }}>
              <div style={{ ...eyebrowStyle(T["--color-text-muted"], 15), letterSpacing: "0.14em" }}>{TRADE_SHARE_COPY.value}</div>
              <div style={{ display: "flex", fontSize: 40, fontWeight: 900, lineHeight: 1.05 }}>{value}</div>
            </div>
          ) : null}
        </div>
      </div>
    );
  }
  return (
    <div style={{ ...frame, alignItems: "center", gap: 14, padding: `0 ${compact ? 12 : 16}px` }}>
      {lead}
      <div style={{ display: "flex", flexDirection: "column", flexGrow: 1, flexShrink: 1, minWidth: 0, gap: 6 }}>
        <div
          style={
            compact
              ? { display: "block", fontSize: nameSize, fontWeight: 800, lineHeight: 1.1, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }
              : { display: "block", fontSize: nameSize, fontWeight: 800, lineHeight: 1.1, lineClamp: 2 }
          }
        >
          {nameText}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10, fontSize: metaSize, fontWeight: 600, color: T["--color-text-muted"] }}>
          {badge}
          <span style={{ display: "block", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{meta.join(" \u00b7 ")}</span>
        </div>
      </div>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 2, flexShrink: 0 }}>
        {isPick ? null : <ShareOvrRing rating={asset.overall_rating} size={ringSize} />}
        {compact || !value ? null : (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 0 }}>
            <div style={{ ...eyebrowStyle(T["--color-text-muted"], 13), letterSpacing: "0.14em" }}>{TRADE_SHARE_COPY.value}</div>
            <div style={{ display: "flex", fontSize: 26, fontWeight: 800, lineHeight: 1.05 }}>{value}</div>
          </div>
        )}
      </div>
    </div>
  );
}

/** One side of the exchange: "YOU SEND" / "YOU GET" label with its colored
 * dot and total (ExchangeSide in the app), then tinted rows. Rows share the
 * panel height equally, so a 1-player side fills the same space a 3-player
 * side does instead of leaving an empty block. */
function ExchangePanel({
  label,
  side,
  total,
  assets,
  rowSize,
  maxRows,
  headshots,
  compact,
  tall,
}: {
  label: string;
  side: Side;
  total: number;
  assets: TradeAsset[];
  rowSize: number;
  maxRows: number;
  headshots: Record<string, string | null>;
  compact: boolean;
  tall: boolean;
}) {
  const shown = assets.slice(0, maxRows);
  const hidden = assets.length - shown.length;
  return (
    <div style={{ display: "flex", flexDirection: "column", flexGrow: 1, flexBasis: 0, minWidth: 0, gap: compact ? 8 : 12 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ display: "flex", width: compact ? 12 : 16, height: compact ? 12 : 16, borderRadius: 16, backgroundColor: SIDE_COLOR[side] }} />
          <div style={{ ...eyebrowStyle(T["--color-text-secondary"], compact ? 18 : 24), letterSpacing: "0.16em" }}>{label}</div>
        </div>
        <div style={{ display: "flex", fontSize: compact ? 28 : 44, fontWeight: 900, lineHeight: 1, color: T["--color-text-primary"] }}>{formatValue(total) || "0"}</div>
      </div>
      <div style={{ display: "flex", flexDirection: "column", flexGrow: 1, gap: compact ? 8 : 12 }}>
        {shown.map((asset, index) => (
          <AssetRow
            key={`${asset.player_id || asset.label || "asset"}-${index}`}
            asset={asset}
            side={side}
            size={rowSize}
            compact={compact}
            tall={tall}
            headshot={asset.player_id ? headshots[asset.player_id] ?? null : null}
          />
        ))}
      </div>
      {hidden > 0 ? <div style={{ display: "flex", fontSize: compact ? 18 : 24, fontWeight: 700, color: T["--color-text-muted"] }}>{`+${hidden} more`}</div> : null}
    </div>
  );
}

/** The two swap arrows between the panels. */
function SwapArrows({ size }: { size: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 48 48" fill="none" stroke={T["--color-accent"]} strokeWidth="4" strokeLinecap="round" strokeLinejoin="round">
      <path d="M8 17h30M30 9l8 8-8 8" />
      <path d="M40 33H10M18 25l-8 8 8 8" />
    </svg>
  );
}

function ConfidenceMeter({ label, size }: { label: string; size: number }) {
  const bars = confidenceBars(label);
  if (!bars) return null;
  const color = bars === 3 ? T["--color-success"] : bars === 2 ? T["--color-action"] : T["--color-warning"];
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: 14,
        padding: `${Math.round(size * 0.3)}px ${Math.round(size * 0.6)}px`,
        borderRadius: shareRadius("--radius-sm"),
        backgroundColor: T["--color-surface-primary"],
        border: `1.5px solid ${T["--color-border"]}`,
      }}
    >
      <div style={{ display: "flex", alignItems: "flex-end", gap: 5, height: size }}>
        {[1, 2, 3].map((n) => (
          <div key={n} style={{ display: "flex", width: Math.round(size * 0.3), height: Math.round(size * (0.4 + n * 0.2)), borderRadius: 3, backgroundColor: n <= bars ? color : T["--color-border-strong"] }} />
        ))}
      </div>
      <div style={{ ...eyebrowStyle(T["--color-text-secondary"], size), letterSpacing: "0.12em" }}>{`${(label || "").trim()} confidence`}</div>
    </div>
  );
}

function VerdictBlock({ idea, compact, includeWhy, why }: { idea: TradeIdea; compact: boolean; includeWhy: boolean; why: string }) {
  const band = (idea.value_edge_band || "").trim();
  const bandColor = band ? resolveTokenColor(fairnessBandColor(band)) : T["--color-text-secondary"];
  const gain = idea.trade_gain;
  // Same Balance line + coloring as TradeIdeaCardView: signed delta, green
  // when it favors you, red when it favors them.
  const balanceColor = gain > 0 ? T["--color-success"] : gain < 0 ? T["--color-danger"] : T["--color-text-secondary"];
  const lowConfidence = (idea.confidence_label || "").trim().toLowerCase() === "low";
  // A softened label never travels without its reason; the numbers are untouched.
  const cautionTag = (idea.caution_tag || "").trim();
  const hasWhy = includeWhy && Boolean(why);
  if (!compact) {
    // One verdict block: chip + confidence on the left, the Balance number
    // on the right, then the plain-English why across the full width.
    return (
      <div style={{ ...glassStyle(), flexDirection: "column", flexShrink: 0, minWidth: 0, padding: "24px 34px", gap: 18, border: `2px solid ${withAlpha(T["--color-accent"], 0.4)}` }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 24 }}>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start", gap: 16 }}>
            {band ? <ShareChip label={band} color={bandColor} size={38} /> : null}
            <ConfidenceMeter label={idea.confidence_label} size={20} />
            {cautionTag ? <div style={{ display: "block", fontSize: 22, fontWeight: 600, lineHeight: 1.2, color: T["--color-warning"] }}>{cautionTag}</div> : null}
          </div>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 6 }}>
            <div style={{ ...eyebrowStyle(T["--color-text-muted"], 22), letterSpacing: "0.16em" }}>{TRADE_SHARE_COPY.balance}</div>
            <div style={{ display: "flex", fontSize: 84, fontWeight: 900, lineHeight: 1, color: balanceColor }}>{formatTradeGain(gain)}</div>
          </div>
        </div>
        {hasWhy ? (
          <>
            <div style={{ display: "flex", height: 2, backgroundColor: T["--color-border"] }} />
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              <div style={{ ...eyebrowStyle(T["--color-accent"], 22), letterSpacing: "0.18em" }}>Why</div>
              <div style={{ display: "block", fontSize: 30, fontWeight: 600, lineHeight: 1.22, color: T["--color-text-primary"] }}>{why}</div>
              {lowConfidence ? <div style={{ display: "block", fontSize: 22, fontWeight: 600, lineHeight: 1.2, color: T["--color-warning"] }}>{LOW_CONFIDENCE_USER_NOTE}</div> : null}
            </div>
          </>
        ) : lowConfidence ? (
          <div style={{ display: "block", fontSize: 22, fontWeight: 600, lineHeight: 1.2, color: T["--color-warning"] }}>{LOW_CONFIDENCE_USER_NOTE}</div>
        ) : null}
      </div>
    );
  }
  return (
    <div style={{ ...glassStyle(), flexGrow: 1, flexShrink: 1, flexBasis: 0, minWidth: 0, alignItems: "stretch", padding: "14px 22px", gap: 22, border: `2px solid ${withAlpha(T["--color-accent"], 0.4)}` }}>
      <div style={{ display: "flex", flexDirection: "column", justifyContent: "center", gap: 8, flexShrink: 0, width: hasWhy ? 330 : "100%" }}>
        {band ? (
          <div style={{ display: "flex" }}>
            <ShareChip label={band} color={bandColor} size={22} />
          </div>
        ) : null}
        <div style={{ display: "flex", alignItems: "baseline", gap: 14 }}>
          <div style={{ ...eyebrowStyle(T["--color-text-muted"], 16), letterSpacing: "0.14em" }}>{TRADE_SHARE_COPY.balance}</div>
          <div style={{ display: "flex", fontSize: 40, fontWeight: 900, lineHeight: 1, color: balanceColor }}>{formatTradeGain(gain)}</div>
        </div>
        <div style={{ display: "flex" }}>
          <ConfidenceMeter label={idea.confidence_label} size={16} />
        </div>
        {cautionTag ? <div style={{ display: "block", fontSize: 14, fontWeight: 600, lineHeight: 1.2, color: T["--color-warning"] }}>{cautionTag}</div> : null}
      </div>
      {hasWhy ? (
        <>
          <div style={{ display: "flex", width: 2, backgroundColor: T["--color-border"] }} />
          <div style={{ display: "flex", flexDirection: "column", justifyContent: "center", gap: 8, flexShrink: 0, width: 300, overflow: "hidden" }}>
            <div style={{ ...eyebrowStyle(T["--color-accent"], 18), letterSpacing: "0.18em" }}>Why</div>
            <div style={{ display: "block", fontSize: 19, fontWeight: 500, lineHeight: 1.25, color: T["--color-text-secondary"] }}>{why}</div>
          </div>
        </>
      ) : null}
    </div>
  );
}

export interface TradePitch {
  headline: string;
  /** Supported facts only; may be empty (then no "why" block is drawn). */
  lines: string[];
  /** Small label above the lines; defaults to the partner pitch's "Why it works for you". */
  eyebrow?: string;
}

function PitchBlock({ pitch, compact }: { pitch: TradePitch; compact: boolean }) {
  return (
    <div style={{ ...glassStyle(), flexGrow: compact ? 1 : 0, flexShrink: 1, flexBasis: compact ? 0 : "auto", minWidth: 0, flexDirection: "column", padding: compact ? "14px 22px" : "28px 32px", gap: compact ? 8 : 16, border: `2px solid ${withAlpha(T["--color-accent"], 0.4)}` }}>
      <div style={{ display: "block", fontSize: compact ? 34 : 52, fontWeight: 900, lineHeight: 1.05, letterSpacing: "-0.02em", lineClamp: 2 }}>{pitch.headline}</div>
      {pitch.lines.length ? (
        <div style={{ display: "flex", flexDirection: "column", gap: compact ? 4 : 10 }}>
          <div style={{ ...eyebrowStyle(T["--color-accent"], compact ? 16 : 22), letterSpacing: "0.18em" }}>{pitch.eyebrow ?? "Why it works for you"}</div>
          {pitch.lines.slice(0, 3).map((line) => (
            <div key={line} style={{ display: "block", fontSize: compact ? 18 : 28, fontWeight: 600, lineHeight: 1.2, color: T["--color-text-secondary"], whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{`• ${line}`}</div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function TradeShareCard({
  idea,
  brand,
  images,
  myTeamName,
  pitch,
  width,
  height,
}: {
  idea: TradeIdea;
  /** Trade Analyzer card: a pitch to the trade partner. Replaces the
   * verdict/edge/confidence block (the sender is advertising the trade, not
   * grading it). `lines` are the supported "why it works for you" facts. */
  pitch?: TradePitch;
  brand: ShareBrandAssets;
  images: TradeCardImages;
  lens?: string;
  /** The signed-in manager's own team name; "Your team" when unknown. */
  myTeamName?: string | null;
  width: number;
  height: number;
}) {
  const compact = height < 900;
  const myTeam = (myTeamName || "").trim() || "Your team";
  const partnerTeam = idea.partner_team_name || "Partner";
  const receive = idea.package.receive ?? [];
  const send = idea.package.send ?? [];
  const maxRows = maxRowsFor(compact);
  const shownRows = Math.min(maxRows, Math.max(send.length, receive.length));
  const tall = !compact && shownRows <= 1;
  const rowSize = compact ? 84 : shownRows <= 2 ? 196 : shownRows === 3 ? 106 : 96;
  // Engine reasons rewritten to plain English, whole sentences only.
  const why = plainTradeWhy(idea.rationale, partnerTeam, compact ? 90 : undefined);
  const avatarSize = compact ? 34 : 72;
  const nameStyle = { display: "block", maxWidth: compact ? 230 : 330, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" } as const;
  const matchup = compact ? (
    <>
      <ShareAvatar src={images.myAvatar ?? null} size={avatarSize} fallbackText={initials(myTeam)} />
      <span style={nameStyle}>{myTeam}</span>
      <SwapArrows size={30} />
      <ShareAvatar src={images.partnerAvatar} size={avatarSize} fallbackText={initials(partnerTeam)} />
      <span style={nameStyle}>{partnerTeam}</span>
    </>
  ) : null;
  const teamHalf = (src: string | null, name: string) => (
    <div style={{ display: "flex", alignItems: "center", gap: 18, flexGrow: 1, flexBasis: 0, minWidth: 0 }}>
      <ShareAvatar src={src} size={avatarSize} fallbackText={initials(name)} />
      <div style={{ display: "block", flexShrink: 1, minWidth: 0, fontSize: name.length > 24 ? 27 : 34, fontWeight: 800, lineHeight: 1.1, lineClamp: 2 }}>{name}</div>
    </div>
  );
  const sendLabel = pitch ? TRADE_SHARE_COPY.pitchSend : TRADE_SHARE_COPY.send;
  const getLabel = pitch ? TRADE_SHARE_COPY.pitchGet : TRADE_SHARE_COPY.get;

  return (
    <ShareFrame
      brand={brand}
      kind="Trade"
      width={width}
      height={height}
      footer={!compact}
      headerRight={compact ? matchup : undefined}
    >
      {compact ? null : (
        <div style={{ ...glassStyle(), alignItems: "center", gap: 20, padding: "18px 26px", flexShrink: 0 }}>
          {teamHalf(images.myAvatar ?? null, myTeam)}
          <SwapArrows size={48} />
          {teamHalf(images.partnerAvatar, partnerTeam)}
        </div>
      )}
      <div style={{ display: "flex", gap: compact ? 24 : 28, flexGrow: 1 }}>
        <ExchangePanel label={sendLabel} side="send" total={idea.send_score} assets={send} rowSize={rowSize} maxRows={maxRows} headshots={images.headshots} compact={compact} tall={tall} />
        <ExchangePanel label={getLabel} side="get" total={idea.receive_score} assets={receive} rowSize={rowSize} maxRows={maxRows} headshots={images.headshots} compact={compact} tall={tall} />
      </div>

      {compact ? (
        <div style={{ display: "flex", gap: 20, alignItems: "stretch" }}>
          {pitch ? <PitchBlock pitch={pitch} compact /> : <VerdictBlock idea={idea} compact includeWhy why={why} />}
          <div style={{ ...glassStyle(), flexShrink: 0, alignItems: "center", gap: 16, padding: "14px 20px" }}>
            <ShareQr brand={brand} size={92} />
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <div style={{ display: "flex", fontSize: 22, fontWeight: 800 }}>{BRAND_DOMAIN}</div>
              <div style={{ display: "flex", fontSize: 16, fontWeight: 500, color: T["--color-text-muted"] }}>{`Scan to try ${BRAND_NAME}`}</div>
            </div>
          </div>
        </div>
      ) : (
        pitch ? <PitchBlock pitch={pitch} compact={false} /> : <VerdictBlock idea={idea} compact={false} includeWhy why={why} />
      )}
    </ShareFrame>
  );
}
