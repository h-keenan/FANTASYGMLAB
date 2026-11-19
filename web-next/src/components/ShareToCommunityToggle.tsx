"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/Button";
import { api, type TradeAsset, type TradeVerdict } from "@/lib/api";
import { Toggle } from "@/components/Toggle";
import { Input } from "@/components/Input";
import { createShareToggleFlow, type ShareToggleFlow } from "@/lib/shareToggleFlow";

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
  // Serializes share and off so that switching off during an in-flight share always wins.

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

  const [flow] = useState<ShareToggleFlow>(() =>
    createShareToggleFlow({ unshare: async (id) => (await api.deleteSharedCommunityTrade(id))?.ok !== false }),
  );

  if (!available) return null;

  const sendShare = async () => {
    const result = await api.shareCommunityTrade({
      send: slimAssets(sendAssets),
      receive: slimAssets(receiveAssets),
      grade: verdict.ui_verdict,
      band: verdict.band,
      why: (verdict.rationale || "").slice(0, 280),
      display_name: name.trim(),
    });
    return result.ok && result.trade ? result.trade.id : null;
  };

  const share = async () => {
    setBusy(true);
    setError("");
    try {
      const outcome = await flow.requestShare(sendShare);
      if (outcome === "shared") setSharedId(flow.sharedId);
      else if (outcome === "unavailable") setError("Sharing isn't available right now.");
      else if (outcome === "error") setError("Could not share this trade.");
      else if (outcome === "stuck-public") {
        setOn(true);
        setSharedId(flow.sharedId);
        setError("Could not stop sharing this trade. Try again.");
      }
    } finally {
      setBusy(false);
    }
  };

  const turnOff = async () => {
    setOn(false);
    setSharedId(null);
    setError("");
    const outcome = await flow.requestOff();
    // A failed delete must not leave the switch saying "off" while the trade is still public.
    if (outcome === "still-public") {
      setOn(true);
      setSharedId(flow.sharedId);
      setError("Could not stop sharing this trade. Try again.");
    }
  };

  return (
    <div
      className="flex flex-col gap-2 p-3"
      style={{ border: "var(--border-width-default) solid var(--color-border)" }}
    >
      <div className="flex items-center justify-between gap-3 text-sm">
        <span style={{ color: "var(--color-text-secondary)" }}>Share to community</span>
        <Toggle
          label="Share to community"
          checked={on}
          onChange={(next) => (next ? setOn(true) : void turnOff())}
        />
      </div>
      {on && !sharedId ? (
        <div className="flex flex-col gap-2">
          <Inpu
            type="text"
            value={name}
            maxLength={24}
            onChange={(event) => setName(event.target.value)}
            placeholder="Display name (optional)"
            aria-label="Display name (optional)"
          />
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            Shows the assets, grade and reason. Blank is Anonymous.
          </span>
          <Button size="sm" loading={busy} onClick={() => void share()}>
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
