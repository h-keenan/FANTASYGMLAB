"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/Button";
import { api, type TradeAsset, type TradeVerdict } from "@/lib/api";

function slimAssets(assets: TradeAsset[]): TradeAsset[] {
  return assets.map((asset) => ({
    asset_type: asset.asset_type,
    player_id: asset.player_id,
    name: asset.name,
    label: asset.label,
    position: asset.position,
  }));
}

/**
 * Opt-in "Share to community" for a Trade Analyzer result. Off by default;
 * nothing is sent until the user turns it on and presses Share. Renders
 * nothing when the shared-trades storage is not set up.
 */
export function ShareToCommunityToggle({
  verdict,
  sendAssets,
  receiveAssets,
}: {
  verdict: TradeVerdict;
  sendAssets: TradeAsset[];
  receiveAssets: TradeAsset[];
}) {
  const [available, setAvailable] = useState(false);
  const [on, setOn] = useState(false);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [sharedId, setSharedId] = useState<string | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    api
      .getSharedCommunityTrades(1)
      .then((result) => {
        if (!cancelled) setAvailable(Boolean(result.available));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  if (!available) return null;

  const share = async () => {
    setBusy(true);
    setError("");
    try {
      const result = await api.shareCommunityTrade({
        send: slimAssets(sendAssets),
        receive: slimAssets(receiveAssets),
        grade: verdict.ui_verdict,
        band: verdict.band,
        why: (verdict.rationale || "").slice(0, 280),
        display_name: name.trim(),
      });
      if (result.ok && result.trade) setSharedId(result.trade.id);
      else setError("Sharing isn't available right now.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not share this trade.");
    } finally {
      setBusy(false);
    }
  };

  const turnOff = async () => {
    const id = sharedId;
    setOn(false);
    setSharedId(null);
    setError("");
    if (id) await api.deleteSharedCommunityTrade(id).catch(() => {});
  };

  return (
    <div
      className="flex flex-col gap-2 p-3"
      style={{ border: "var(--border-width-default) solid var(--color-border)" }}
    >
      <label className="flex items-center justify-between gap-3 text-sm">
        <span style={{ color: "var(--color-text-secondary)" }}>Share to community</span>
        <input
          type="checkbox"
          role="switch"
          aria-checked={on}
          checked={on}
          disabled={busy}
          onChange={(event) => (event.target.checked ? setOn(true) : void turnOff())}
        />
      </label>
      {on && !sharedId ? (
        <div className="flex flex-col gap-2">
          <input
            type="text"
            value={name}
            maxLength={24}
            onChange={(event) => setName(event.target.value)}
            placeholder="Display name (optional)"
            aria-label="Display name (optional)"
            className="px-2 py-1 text-sm"
            style={{
              background: "var(--color-surface-muted)",
              border: "var(--border-width-default) solid var(--color-border)",
              color: "var(--color-text-primary)",
            }}
          />
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            Shows the assets, grade and reason. Blank is Anonymous.
          </span>
          <Button size="sm" disabled={busy} onClick={() => void share()}>
            {busy ? "Sharing…" : "Share"}
          </Button>
        </div>
      ) : null}
      {sharedId ? (
        <span className="text-xs" style={{ color: "var(--color-success)" }}>
          Shared. Turn off to remove it.
        </span>
      ) : null}
      {error ? (
        <span role="alert" className="text-xs" style={{ color: "var(--color-danger)" }}>
          {error}
        </span>
      ) : null}
    </div>
  );
}
