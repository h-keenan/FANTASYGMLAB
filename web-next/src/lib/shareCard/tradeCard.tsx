/**
 * Trade idea share card: two "RECEIVES" panels (your team / the partner)
 * with swap arrows between them, the value-edge verdict with a confidence
 * meter, the server's own rationale, and the QR footer. Every field comes
 * straight off the server's TradeIdea (GET .../trade-hub), the same object
 * the in-app TradeIdeaCardView renders; nothing here is derived beyond
 * formatting. No NFL marks: team identity is the manager's own Sleeper
 * avatar (which the app already shows) or initials.
 *
 * Two sizes: 1080x1350 (stories/posts) and 1200x630 (link unfurls).
 */

import type { TradeAsset, TradeIdea } from "@/lib/api";
import { fairnessBandColor } from "@/lib/tradeHubPresentation";

import {
  ShareAvatar,
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

/** Trim the rationale at a word boundary so the clamp never cuts mid-word. */
export function clampText(text: string, max: number): string {
  const clean = text.replace(/\s+/g, " ").trim();
  if (clean.length <= max) return clean;
  const cut = clean.slice(0, max);
  return `${cut.slice(0, Math.max(cut.lastIndexOf(" "), max - 20)).replace(/[\s,.;:-]+$/, "")}…`;
}

/** Who the value edge favors, with the amount. */
export function edgeSummary(gain: number, myTeam: string, partnerTeam: string): { text: string; color: string } {
  if (!gain) return { text: "Even value", color: T["--color-text-secondary"] };
  const amount = Math.abs(Math.round(gain)).toLocaleString("en-US");
  return gain > 0
    ? { text: `Edge: ${myTeam} +${amount}`, color: T["--color-success"] }
    : { text: `Edge: ${partnerTeam} +${amount}`, color: T["--color-danger"] };
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

function AssetRow({ asset, size, headshot }: { asset: TradeAsset; size: number; headshot: string | null }) {
  const isPick = asset.asset_type === "pick";
  const nameSize = Math.round(size * 0.25);
  const metaSize = Math.round(size * 0.2);
  const value = formatValue(asset.score);
  const meta: string[] = [];
  if (isPick) {
    meta.push(value ? `${value} value` : "Draft pick");
    if (asset.owner_team_name && asset.owner_team_name.length <= 10) meta.push(`via ${asset.owner_team_name}`);
  } else {
    meta.push(asset.team || "FA");
  }
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        gap: Math.round(size * 0.14),
        height: size,
        padding: `0 ${Math.round(size * 0.1)}px`,
        borderRadius: shareRadius("--radius-md"),
        backgroundColor: "rgba(255, 255, 255, 0.045)",
        border: `1.5px solid ${T["--color-border"]}`,
      }}
    >
      {isPick ? (
        <PickPlate asset={asset} size={Math.round(size * 0.62)} />
      ) : (
        <ShareAvatar src={headshot} tier={asset.tier} size={Math.round(size * 0.62)} fallbackText={initials(asset.name)} />
      )}
      <div style={{ display: "flex", flexDirection: "column", flexGrow: 1, flexShrink: 1, minWidth: 0, gap: Math.round(size * 0.06) }}>
        <div style={{ display: "block", fontSize: nameSize, fontWeight: 800, lineHeight: 1.12, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
          {isPick ? pickTitle(asset) : asset.name || "Unknown player"}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 10, fontSize: metaSize, fontWeight: 600, color: T["--color-text-muted"] }}>
          {isPick ? null : <SharePositionBadge position={asset.position} size={Math.round(metaSize * 0.9)} />}
          <span style={{ display: "block", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{meta.join(" · ")}</span>
        </div>
      </div>
      {isPick ? null : <ShareOvrRing rating={asset.overall_rating} size={Math.round(size * 0.46)} />}
    </div>
  );
}

function ReceivesPanel({
  teamName,
  avatar,
  accent,
  total,
  assets,
  rowSize,
  maxRows,
  headshots,
  compact,
}: {
  teamName: string;
  avatar: string | null;
  accent: string;
  total: number;
  assets: TradeAsset[];
  rowSize: number;
  maxRows: number;
  headshots: Record<string, string | null>;
  compact: boolean;
}) {
  const shown = assets.slice(0, maxRows);
  const hidden = assets.length - shown.length;
  const avatarSize = compact ? 44 : 60;
  return (
    <div
      style={{
        ...glassStyle(),
        flexDirection: "column",
        flexGrow: 1,
        flexBasis: 0,
        minWidth: 0,
        padding: compact ? "16px 18px" : "24px 20px",
        gap: compact ? 8 : 12,
        border: `2px solid ${withAlpha(accent, 0.55)}`,
      }}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: compact ? 2 : 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <ShareAvatar src={avatar} size={avatarSize} fallbackText={initials(teamName)} />
          <div
            style={{
              display: "block",
              flexGrow: 1,
              flexShrink: 1,
              minWidth: 0,
              fontSize: compact ? 22 : 28,
              fontWeight: 900,
              lineHeight: 1.1,
              color: accent,
              textTransform: "uppercase",
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {teamName}
          </div>
        </div>
        {(
          <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
            <div style={{ ...eyebrowStyle(T["--color-text-muted"], compact ? 15 : 20), letterSpacing: "0.2em" }}>Receives</div>
            <div style={{ display: "flex", fontSize: compact ? 32 : 52, fontWeight: 900, lineHeight: 1 }}>{formatValue(total) || "0"}</div>
          </div>
        )}
      </div>
      {shown.map((asset, index) => (
        <AssetRow
          key={`${asset.player_id || asset.label || "asset"}-${index}`}
          asset={asset}
          size={rowSize}
          headshot={asset.player_id ? headshots[asset.player_id] ?? null : null}
        />
      ))}
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

function VerdictBlock({
  idea,
  myTeam,
  compact,
  includeWhy,
  why,
}: {
  idea: TradeIdea;
  myTeam: string;
  compact: boolean;
  includeWhy: boolean;
  why: string;
}) {
  const band = (idea.value_edge_band || "").trim();
  const bandColor = band ? resolveTokenColor(fairnessBandColor(band)) : T["--color-text-primary"];
  const edge = edgeSummary(idea.trade_gain, myTeam, idea.partner_team_name);
  return (
    <div style={{ ...glassStyle(), flexGrow: compact ? 1 : 0, flexShrink: 1, flexBasis: compact ? 0 : "auto", minWidth: 0, alignItems: "stretch", padding: compact ? "14px 22px" : "28px 32px", gap: compact ? 22 : 30, border: `2px solid ${withAlpha(T["--color-accent"], 0.4)}` }}>
      <div style={{ display: "flex", flexDirection: "column", justifyContent: "center", gap: compact ? 8 : 14, flexShrink: 0, width: includeWhy && why ? (compact ? 370 : 400) : "100%" }}>
        <div style={{ display: "flex", fontSize: compact ? 48 : 70, fontWeight: 900, lineHeight: 1.02, color: bandColor, letterSpacing: "-0.02em" }}>{band || "Trade idea"}</div>
        <div style={{ display: "block", fontSize: compact ? 22 : 26, fontWeight: 800, color: edge.color, lineClamp: 2 }}>
          {edge.text}
        </div>
        <div style={{ display: "flex" }}>
          <ConfidenceMeter label={idea.confidence_label} size={compact ? 16 : 22} />
        </div>
      </div>
      {includeWhy && why ? (
        <>
          <div style={{ display: "flex", width: 2, backgroundColor: T["--color-border"] }} />
          <div style={{ display: "flex", flexDirection: "column", justifyContent: "center", gap: compact ? 8 : 14, flexShrink: 0, width: compact ? 324 : 426, paddingLeft: compact ? 18 : 26, overflow: "hidden" }}>
            <div style={{ ...eyebrowStyle(T["--color-accent"], compact ? 18 : 24), letterSpacing: "0.18em" }}>Why</div>
            <div style={{ display: "block", fontSize: compact ? 19 : 25, fontWeight: 500, lineHeight: 1.25, color: T["--color-text-secondary"], lineClamp: compact ? 4 : 6 }}>{why}</div>
          </div>
        </>
      ) : null}
    </div>
  );
}

export function TradeShareCard({
  idea,
  brand,
  images,
  myTeamName,
  width,
  height,
}: {
  idea: TradeIdea;
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
  const rowSize = compact ? 66 : shownRows <= 2 ? 120 : shownRows === 3 ? 108 : 96;
  const rationale = (idea.rationale || "").trim() || (idea.reasoning_tags ?? []).join(" · ");
  const why = clampText(rationale, compact ? 125 : 200);
  const arrowSize = compact ? 56 : 76;
  const nameStyle = { display: "block", maxWidth: compact ? 300 : 420, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" } as const;
  const matchup = (
    <>
      <span style={nameStyle}>{myTeam}</span>
      <SwapArrows size={compact ? 30 : 40} />
      <span style={nameStyle}>{partnerTeam}</span>
    </>
  );

  return (
    <ShareFrame
      brand={brand}
      kind="Trade"
      width={width}
      height={height}
      footer={!compact}
      headerRight={compact ? matchup : undefined}
    >
      {compact ? null : <div style={{ display: "flex", alignItems: "center", gap: 14, fontSize: 38, fontWeight: 700 }}>{matchup}</div>}
      <div style={{ display: "flex", flexGrow: 1, position: "relative", gap: compact ? 44 : 56 }}>
        <ReceivesPanel
          teamName={myTeam}
          avatar={images.myAvatar ?? null}
          accent={T["--color-accent"]}
          total={idea.receive_score}
          assets={receive}
          rowSize={rowSize}
          maxRows={maxRows}
          headshots={images.headshots}
          compact={compact}
        />
        <ReceivesPanel
          teamName={partnerTeam}
          avatar={images.partnerAvatar}
          accent={T["--color-action"]}
          total={idea.send_score}
          assets={send}
          rowSize={rowSize}
          maxRows={maxRows}
          headshots={images.headshots}
          compact={compact}
        />
        <div style={{ display: "flex", position: "absolute", top: "40%", left: "50%", marginLeft: -arrowSize / 2, width: arrowSize, height: arrowSize, alignItems: "center", justifyContent: "center", borderRadius: arrowSize, backgroundColor: T["--color-bg"], border: `2px solid ${withAlpha(T["--color-accent"], 0.5)}` }}>
          <SwapArrows size={Math.round(arrowSize * 0.62)} />
        </div>
      </div>

      {compact ? (
        <div style={{ display: "flex", gap: 20, alignItems: "stretch" }}>
          <VerdictBlock idea={idea} myTeam={myTeam} compact includeWhy why={why} />
          <div style={{ ...glassStyle(), flexShrink: 0, alignItems: "center", gap: 16, padding: "14px 20px" }}>
            <ShareQr brand={brand} size={92} />
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              <div style={{ display: "flex", fontSize: 22, fontWeight: 800 }}>{BRAND_DOMAIN}</div>
              <div style={{ display: "flex", fontSize: 16, fontWeight: 500, color: T["--color-text-muted"] }}>{`Scan to try ${BRAND_NAME}`}</div>
            </div>
          </div>
        </div>
      ) : (
        <VerdictBlock idea={idea} myTeam={myTeam} compact={false} includeWhy why={why} />
      )}
    </ShareFrame>
  );
}
