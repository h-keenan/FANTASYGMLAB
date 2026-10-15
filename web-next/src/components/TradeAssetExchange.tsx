import type { TradeAsset } from "@/lib/api";
import { OvrGauge } from "@/components/OvrGauge";
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

export function TradeAssetRow({ asset }: { asset: TradeAsset }) {
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
      <OvrGauge rating={asset.overall_rating ?? null} size="sm" />
      <PositionBadge position={asset.position} />
      <div className="flex flex-col min-w-0">
        <span className="text-sm font-bold truncate" style={{ color: "var(--color-text-primary)" }}>
          {asset.name || "Player"}
        </span>
        <span className="text-xs truncate" style={{ color: "var(--color-text-muted)" }}>
          {[asset.team, asset.age ? `Age ${asset.age}` : null].filter(Boolean).join(" · ") || "Player"}
        </span>
      </div>
      {asset.score !== null && asset.score !== undefined ? (
        <span className="ml-auto text-xs font-bold shrink-0" style={{ color: "var(--color-text-muted)" }}>
          {formatValue(asset.score)}
        </span>
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
        <div className="flex flex-col divide-y" style={{ borderColor: "var(--color-border)" }}>
          {assets.map((asset, index) => (
            <TradeAssetRow key={asset.player_id || asset.label || index} asset={asset} />
          ))}
        </div>
      )}
    </div>
  );
}
