import type { TradeAsset } from "@/lib/api";
import { OvrGauge } from "@/components/OvrGauge";
import { PlayerIdentity } from "@/components/PlayerRow";
import { ValueStat } from "@/components/ValueStat";

/**
 * Shared give/get asset row + labeled exchange-side column — extracted
 * (Revision 9 CSS-cleanup pass) from TradeHubContent.tsx's own local
 * TradeAssetRow/ExchangeSide so GM Plan's Trade Opportunities cards (which
 * render the exact same send_assets/receive_assets TradeAsset dicts
 * modules.gm_plan now carries, just one idea per card instead of Trade
 * Hub's ranked board) don't duplicate this markup a second time.
 */

function formatValue(raw: number | null | undefined): string {
  if (raw === null || raw === undefined) return "";
  return Math.round(raw).toLocaleString();
}

/**
 * The square draft-pick plate ("R1" over "#3"). One look for every pick row:
 * TradeAssetRow's pick branch and PickRow both render it.
 */
export function PickPlate({ round, pickNo }: { round?: number | string | null; pickNo?: number | string | null }) {
  const top = round ? `R${round}` : pickNo ? `#${pickNo}` : "PICK";
  const bottom = round && pickNo ? `#${pickNo}` : null;
  return (
    <div
      className="flex flex-col items-center justify-center font-extrabold uppercase leading-none"
      style={{
        width: "2.25rem",
        height: "2.25rem",
        flex: "0 0 2.25rem",
        fontSize: "0.6875rem",
        gap: 2,
        background: "var(--color-surface-muted)",
        border: "var(--border-width-default) solid var(--color-border)",
        color: "var(--color-accent)",
      }}
    >
      <span>{top}</span>
      {bottom ? <span>{bottom}</span> : null}
    </div>
  );
}

export function TradeAssetRow({
  asset,
  disableQuickView = false,
}: {
  asset: TradeAsset;
  /** Some callers (TradeAnalyzerContent's own add/remove pickers) already
   * wrap this row in their OWN real `<button onClick=.../>` for a
   * different action (add/remove this asset from a package). A `<button>`
   * can't legally nest inside a `<button>`, and even if it rendered, a tap
   * would ambiguously mean two different things at once — so those callers
   * pass `disableQuickView` to get the original plain, non-interactive
   * row back, same as before this modal existed. Every read-only display
   * of this row (ExchangeSide / GM Plan / Trade Hub / Live Draft Trade
   * Evaluator / Trade History) leaves this false. */
  disableQuickView?: boolean;
}) {
  if (asset.asset_type === "pick") {
    return (
      <div className="flex items-center gap-3 py-1.5">
        <PickPlate round={asset.round} pickNo={asset.pick_no} />
        <div className="flex flex-col min-w-0">
          <span className="text-sm font-bold truncate" style={{ color: "var(--color-text-primary)" }}>
            {asset.label || "Draft pick"}
          </span>
          {asset.owner_team_name || asset.projected_range ? (
            <span className="text-xs truncate" style={{ color: "var(--color-text-muted)" }}>
              {[asset.projected_range, asset.owner_team_name].filter(Boolean).join(" · ")}
            </span>
          ) : null}
        </div>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-3 py-1.5">
      <PlayerIdentity
        identity={asset.player_id ? { ...asset, player_id: asset.player_id, sourceLabel: "Trade Board" } : null}
        playerId={asset.player_id}
        name={asset.name || "Player"}
        position={asset.position}
        tier={asset.tier}
        injuryStatus={asset.injury_status}
        disableQuickView={disableQuickView}
      >
        {[asset.team, asset.age ? `Age ${asset.age}` : null].filter(Boolean).join(" · ") || "Player"}
      </PlayerIdentity>
      {asset.score !== null && asset.score !== undefined ? (
        <div className="ml-auto flex items-center gap-2 shrink-0">
          <OvrGauge rating={asset.overall_rating ?? null} size="sm" />
          <ValueStat value={formatValue(asset.score)} />
        </div>
      ) : null}
    </div>
  );
}

export function ExchangeSide({
  label,
  dotColor,
  assets,
  total,
}: {
  label: string;
  dotColor: string;
  assets: TradeAsset[];
  /** Optional side total shown at the right of the label row. */
  total?: { text: string; color: string };
}) {
  return (
    <div className="flex flex-col gap-1 min-w-0">
      <div className="flex items-center gap-1.5">
        <span className="inline-block" style={{ width: 6, height: 6, borderRadius: "50%", background: dotColor }} />
        <span
          className="uppercase text-xs font-bold"
          style={{ letterSpacing: "var(--letter-spacing-badge)", color: "var(--color-text-muted)" }}
        >
          {label}
        </span>
        {total ? (
          <span className="ml-auto text-sm font-black" style={{ color: total.color, fontVariantNumeric: "tabular-nums" }}>
            {total.text}
          </span>
        ) : null}
      </div>
      {assets.length === 0 ? (
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          None selected
        </span>
      ) : (
        // coridian_, 2026-10-18: "either a background for the header of
        // this module or the footer or a background color behind the
        // players you're sending or giving" — a faint tint of the side's
        // own send/get dot color gives each side a real visual boundary
        // instead of bare rows on the card's own background. First pass
        // reused the shared -soft tokens (~15% alpha) — right for a small
        // pill/badge, but coridian_, same day, on this exact change: "the
        // red and green background I think is a little too strong" once
        // it covered a whole block instead of a chip. A plain color-mix at
        // a much lower percentage reads as a boundary, not a solid fill.
        <div
          className="flex flex-col divide-y px-2 py-1"
          style={{
            borderColor: "var(--color-border)",
            background: `color-mix(in srgb, ${dotColor} 6%, transparent)`,
          }}
        >
          {assets.map((asset, index) => (
            <TradeAssetRow key={asset.player_id || asset.label || index} asset={asset} />
          ))}
        </div>
      )}
    </div>
  );
}
