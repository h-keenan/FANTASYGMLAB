import type { TradeAsset } from "@/lib/api";
import { OvrGauge } from "@/components/OvrGauge";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { PlayerIdentityTrigger } from "@/components/PlayerIdentityTrigger";
import { PositionBadge } from "@/components/PositionBadge";

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
    const plate = asset.pick_no ? `#${asset.pick_no}` : asset.round ? `R${asset.round}` : "PICK";
    return (
      <div className="flex items-center gap-3 py-1.5">
        <div
          className="flex items-center justify-center text-xs font-extrabold uppercase"
          style={{
            width: "2.25rem",
            height: "2.25rem",
            flex: "0 0 2.25rem",
            background: "var(--color-surface-muted)",
            border: "var(--border-width-default) solid var(--color-border)",
            color: "var(--color-accent)",
          }}
        >
          {plate}
        </div>
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
      {asset.player_id && !disableQuickView ? (
        <PlayerIdentityTrigger
          identity={{ ...asset, player_id: asset.player_id, sourceLabel: "Trade Board" }}
          className="flex items-center gap-3 min-w-0"
        >
          <PositionBadge position={asset.position} />
          <PlayerAvatar playerId={asset.player_id} tier={asset.tier} size={40} />
          <div className="flex flex-col min-w-0">
            <span className="text-sm font-bold truncate" style={{ color: "var(--color-text-primary)" }}>
              {asset.name || "Player"}
            </span>
            <span className="text-xs truncate" style={{ color: "var(--color-text-muted)" }}>
              {[asset.team, asset.age ? `Age ${asset.age}` : null].filter(Boolean).join(" · ") || "Player"}
            </span>
          </div>
        </PlayerIdentityTrigger>
      ) : (
        <>
          <PositionBadge position={asset.position} />
          <PlayerAvatar playerId={asset.player_id} tier={asset.tier} size={40} />
          <div className="flex flex-col min-w-0">
            <span className="text-sm font-bold truncate" style={{ color: "var(--color-text-primary)" }}>
              {asset.name || "Player"}
            </span>
            <span className="text-xs truncate" style={{ color: "var(--color-text-muted)" }}>
              {[asset.team, asset.age ? `Age ${asset.age}` : null].filter(Boolean).join(" · ") || "Player"}
            </span>
          </div>
        </>
      )}
      {asset.score !== null && asset.score !== undefined ? (
        <div className="ml-auto flex items-center gap-2 shrink-0">
          <OvrGauge rating={asset.overall_rating ?? null} size="sm" />
          {/* coridian_, 2026-10-18: "the value on the far right should not
              be gray" — this is the player's actual trade value, not a
              muted caption, so it reads at full text-primary strength like
              the name beside it. */}
          <span className="text-xs font-bold" style={{ color: "var(--color-text-primary)" }}>
            {formatValue(asset.score)}
          </span>
        </div>
      ) : null}
    </div>
  );
}

export function ExchangeSide({
  label,
  dotColor,
  assets,
}: {
  label: string;
  dotColor: string;
  assets: TradeAsset[];
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
      </div>
      {assets.length === 0 ? (
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          None selected
        </span>
      ) : (
        // coridian_, 2026-10-18: "either a background for the header of
        // this module or the footer or a background color behind the
        // players you're sending or giving" — a faint tint of the side's
        // own send/get dot color (same -soft tokens the rest of the app
        // already uses for risk/success panels, not a new color) gives
        // each side a real visual boundary instead of bare rows on the
        // card's own background.
        <div
          className="flex flex-col divide-y px-2 py-1"
          style={{
            borderColor: "var(--color-border)",
            background: dotColor === "var(--color-danger)" ? "var(--color-danger-soft)" : "var(--color-success-soft)",
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
