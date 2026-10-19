"use client";

import { useEffect, useMemo, useState } from "react";

import { api, type LiveDraftPickOption, type LiveDraftPickRow } from "@/lib/api";
import { ExchangeSide } from "@/components/TradeAssetExchange";
import { fairnessBandColor, formatTradeGain } from "@/lib/tradeHubPresentation";
import { liveDraftAssetToTradeAsset, liveDraftDraftedPlayerOptions } from "@/lib/liveDraftPresentation";

/**
 * Hypothetical mid-draft Trade Evaluator — the last of the 4 deferred
 * pieces from the migration sprint. Ports modules/live_draft_ui.py's
 * `_render_trade_evaluator` form: propose a send/receive package of
 * not-yet-made picks and already-drafted players, get back the same
 * Favorable / Fair / Slight Overpay / Major Overpay verdict the standalone
 * Trade Calculator uses (modules/live_draft_trade_evaluator.py — no
 * valuation logic reimplemented here).
 *
 * Layout follows Streamlit's own send/receive multiselect form rather than
 * Trade Analyzer's roster-browse builder (TradeAnalyzerContent.tsx):
 * neither side here has a known value until the server scores the whole
 * package (a not-yet-made pick's price depends on draft-state-aware team
 * strength, and this module deliberately shows no per-item preview before
 * that, same as Streamlit), so there's nothing to browse/search by score —
 * only two label-only checklists per side, matching the real page exactly.
 * Once scored, the result reuses Trade Analyzer's own
 * ExchangeSide/TradeAssetRow for the give/get matchup, and Trade Hub's
 * fairnessBandColor/formatTradeGain for the value-edge badge — same
 * send/receive + banded-delta language as the app's two other trade
 * surfaces, just without the lean bar/confidence ring Trade Analyzer's
 * fuller fit-engine verdict has (this module's evaluate_trade has no
 * confidence score to show — see modules/trade_visual_language.py's
 * value_edge_html docstring on why Live Draft's evaluator is one of the
 * few callers that keeps only the inline magnitude mark).
 */

function CheckList({
  label,
  options,
  selected,
  onToggle,
  emptyLabel,
}: {
  label: string;
  options: { key: string; label: string }[];
  selected: Set<string>;
  onToggle: (key: string) => void;
  emptyLabel: string;
}) {
  return (
    <div className="flex flex-col gap-1 min-w-0">
      <span
        className="text-xs font-bold uppercase"
        style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}
      >
        {label}
      </span>
      {options.length === 0 ? (
        <span className="text-xs italic" style={{ color: "var(--color-text-muted)" }}>
          {emptyLabel}
        </span>
      ) : (
        <div
          className="flex flex-col max-h-48 overflow-y-auto"
          style={{ border: "var(--border-width-default) solid var(--color-border)" }}
        >
          {options.map((option) => {
            const checked = selected.has(option.key);
            return (
              <button
                key={option.key}
                type="button"
                onClick={() => onToggle(option.key)}
                aria-pressed={checked}
                className="flex items-center gap-2 px-2 py-1.5 text-left text-xs"
                style={{
                  background: checked ? "var(--color-accent-soft)" : "transparent",
                  color: checked ? "var(--color-accent)" : "var(--color-text-secondary)",
                  borderBottom: "var(--border-width-default) solid var(--color-border)",
                }}
              >
                <span
                  aria-hidden="true"
                  className="shrink-0 inline-block"
                  style={{
                    width: 14,
                    height: 14,
                    border: `var(--border-width-default) solid ${checked ? "var(--color-accent)" : "var(--color-border)"}`,
                    background: checked ? "var(--color-accent)" : "transparent",
                  }}
                />
                <span className="truncate font-bold">{option.label}</span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

function toggleKey(set: Set<string>, key: string): Set<string> {
  const next = new Set(set);
  if (next.has(key)) next.delete(key);
  else next.add(key);
  return next;
}

interface EvaluatorResult {
  send_assets: ReturnType<typeof liveDraftAssetToTradeAsset>[];
  receive_assets: ReturnType<typeof liveDraftAssetToTradeAsset>[];
  delta: number;
  verdict: string;
}

export function LiveDraftTradeEvaluator({
  leagueId,
  draftId,
  draftedRows,
  lens = "Dynasty",
}: {
  leagueId: string;
  draftId: string;
  draftedRows: LiveDraftPickRow[];
  lens?: string;
}) {
  const [open, setOpen] = useState(false);
  const [pickOptions, setPickOptions] = useState<LiveDraftPickOption[]>([]);
  const [optionsError, setOptionsError] = useState<string | null>(null);
  // Which draftId pickOptions was actually loaded for — compared against
  // the current draftId below to derive "still loading" without a second
  // piece of state set synchronously at the top of the effect (React 19's
  // react-hooks/set-state-in-effect rule flags that pattern; see
  // PlayerCompareContent.tsx's modelsLoadedFor for the same fix).
  const [pickOptionsLoadedFor, setPickOptionsLoadedFor] = useState<string | null>(null);

  const [sendPickKeys, setSendPickKeys] = useState<Set<string>>(new Set());
  const [receivePickKeys, setReceivePickKeys] = useState<Set<string>>(new Set());
  const [sendPlayerIds, setSendPlayerIds] = useState<Set<string>>(new Set());
  const [receivePlayerIds, setReceivePlayerIds] = useState<Set<string>>(new Set());

  const [evaluating, setEvaluating] = useState(false);
  const [result, setResult] = useState<EvaluatorResult | null>(null);
  const [evalError, setEvalError] = useState<string | null>(null);
  const [staleKeys, setStaleKeys] = useState<string[]>([]);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    api
      .getLiveDraftTradeEvaluatorOptions(leagueId, draftId)
      .then((response) => {
        if (cancelled) return;
        setPickOptions(response.pick_options);
        setOptionsError(null);
        setPickOptionsLoadedFor(draftId);
      })
      .catch((err) => {
        if (cancelled) return;
        setOptionsError(err instanceof Error ? err.message : "Could not load the remaining picks.");
        setPickOptionsLoadedFor(draftId);
      });
    return () => {
      cancelled = true;
    };
  }, [open, leagueId, draftId]);

  const loadingOptions = open && pickOptionsLoadedFor !== draftId;

  const playerOptions = useMemo(() => liveDraftDraftedPlayerOptions(draftedRows), [draftedRows]);
  const pickCheckOptions = useMemo(
    () => pickOptions.map((option) => ({ key: option.pick_key, label: option.label })),
    [pickOptions],
  );
  const pickLabelByKey = useMemo(() => {
    const map: Record<string, string> = {};
    for (const option of pickOptions) map[option.pick_key] = option.label;
    return map;
  }, [pickOptions]);

  function clearVerdict() {
    setResult(null);
    setEvalError(null);
    setStaleKeys([]);
  }

  const overlap =
    [...sendPickKeys].some((key) => receivePickKeys.has(key)) ||
    [...sendPlayerIds].some((id) => receivePlayerIds.has(id));
  const sendHasAssets = sendPickKeys.size > 0 || sendPlayerIds.size > 0;
  const receiveHasAssets = receivePickKeys.size > 0 || receivePlayerIds.size > 0;
  const canEvaluate = sendHasAssets && receiveHasAssets && !overlap;

  async function evaluate() {
    setEvaluating(true);
    clearVerdict();
    try {
      const response = await api.postLiveDraftTradeEvaluator(leagueId, draftId, {
        sendPickKeys: [...sendPickKeys],
        receivePickKeys: [...receivePickKeys],
        sendPlayerIds: [...sendPlayerIds],
        receivePlayerIds: [...receivePlayerIds],
        lens,
      });
      if (response.reason === "stale_picks") {
        setStaleKeys(response.stale_pick_keys);
      } else if (response.reason === "assets_not_found") {
        setEvalError("One of the selected assets could not be resolved. Remove it and try again.");
      } else if (response.reason === "no_player_data") {
        setEvalError("Player data isn't available right now — try again in a bit.");
      } else {
        setResult({
          send_assets: (response.send_assets ?? []).map(liveDraftAssetToTradeAsset),
          receive_assets: (response.receive_assets ?? []).map(liveDraftAssetToTradeAsset),
          delta: response.delta ?? 0,
          verdict: response.verdict ?? "Fair",
        });
      }
    } catch (err) {
      setEvalError(err instanceof Error ? err.message : "Could not evaluate this trade.");
    } finally {
      setEvaluating(false);
    }
  }

  const toneColor = result ? fairnessBandColor(result.verdict) : "var(--color-text-secondary)";

  return (
    <section
      className="glass-surface flex flex-col gap-3 p-4"
    >
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div className="flex flex-col gap-0.5">
          <h2 style={{ font: "var(--type-section-title)" }}>Trade Evaluator</h2>
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            Hypothetical only — nothing is sent to Sleeper.
          </span>
        </div>
        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          className="px-3 py-2 text-sm font-bold"
          style={{ color: "var(--color-accent)", border: "var(--border-width-default) solid var(--color-border)" }}
        >
          {open ? "Hide" : "Evaluate a trade"}
        </button>
      </div>

      {open ? (
        loadingOptions ? (
          <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
            Loading remaining picks…
          </p>
        ) : optionsError ? (
          <p role="alert" style={{ color: "var(--color-danger)" }}>
            {optionsError}
          </p>
        ) : (
          <>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="flex flex-col gap-2">
                <span className="text-xs font-bold uppercase" style={{ color: "var(--color-danger)" }}>
                  You send
                </span>
                <CheckList
                  label="Remaining picks"
                  options={pickCheckOptions}
                  selected={sendPickKeys}
                  onToggle={(key) => {
                    setSendPickKeys((prev) => toggleKey(prev, key));
                    clearVerdict();
                  }}
                  emptyLabel="No remaining picks are open."
                />
                <CheckList
                  label="Drafted players"
                  options={playerOptions}
                  selected={sendPlayerIds}
                  onToggle={(id) => {
                    setSendPlayerIds((prev) => toggleKey(prev, id));
                    clearVerdict();
                  }}
                  emptyLabel="No players have been drafted yet."
                />
              </div>
              <div className="flex flex-col gap-2">
                <span className="text-xs font-bold uppercase" style={{ color: "var(--color-success)" }}>
                  You receive
                </span>
                <CheckList
                  label="Remaining picks"
                  options={pickCheckOptions}
                  selected={receivePickKeys}
                  onToggle={(key) => {
                    setReceivePickKeys((prev) => toggleKey(prev, key));
                    clearVerdict();
                  }}
                  emptyLabel="No remaining picks are open."
                />
                <CheckList
                  label="Drafted players"
                  options={playerOptions}
                  selected={receivePlayerIds}
                  onToggle={(id) => {
                    setReceivePlayerIds((prev) => toggleKey(prev, id));
                    clearVerdict();
                  }}
                  emptyLabel="No players have been drafted yet."
                />
              </div>
            </div>

            {overlap ? (
              <p role="alert" className="text-xs" style={{ color: "var(--color-danger)" }}>
                The same pick or player can&apos;t be on both sides of a trade.
              </p>
            ) : null}

            <button
              type="button"
              onClick={evaluate}
              disabled={!canEvaluate || evaluating}
              className="self-start px-4 py-2 text-sm font-bold"
              style={{
                background: canEvaluate ? "var(--color-accent)" : "var(--color-surface-muted)",
                color: canEvaluate ? "#fff" : "var(--color-text-muted)",
              }}
            >
              {evaluating ? "Evaluating…" : "Evaluate Trade"}
            </button>

            {staleKeys.length > 0 ? (
              <p role="alert" className="text-sm" style={{ color: "var(--color-danger)" }}>
                These picks were just selected and can no longer be evaluated:{" "}
                {staleKeys.map((key) => pickLabelByKey[key] ?? key).join(", ")}. Refresh the selections above and
                re-submit.
              </p>
            ) : null}
            {evalError ? (
              <p role="alert" className="text-sm" style={{ color: "var(--color-danger)" }}>
                {evalError}
              </p>
            ) : null}

            {result ? (
              <div
                className="flex flex-col gap-3 p-3"
                style={{ background: "var(--color-surface-raised)", border: "var(--border-width-default) solid var(--color-border)" }}
              >
                <div className="grid grid-cols-1 sm:grid-cols-[minmax(0,1fr)_1.5rem_minmax(0,1fr)] gap-3 items-start">
                  <ExchangeSide label="You send" dotColor="var(--color-danger)" assets={result.send_assets} />
                  <div
                    className="hidden sm:flex items-center justify-center text-xs font-bold uppercase self-stretch"
                    style={{ color: "var(--color-accent)" }}
                    aria-hidden="true"
                  >
                    FOR
                  </div>
                  <ExchangeSide label="You receive" dotColor="var(--color-success)" assets={result.receive_assets} />
                </div>
                <div className="flex items-baseline gap-2 flex-wrap">
                  <span
                    className="text-xs uppercase font-bold"
                    style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}
                  >
                    Trade value
                  </span>
                  <span className="text-2xl font-black" style={{ color: toneColor, fontVariantNumeric: "tabular-nums" }}>
                    {formatTradeGain(result.delta)}
                  </span>
                  <span className="text-xs font-bold uppercase" style={{ color: toneColor }}>
                    {result.verdict}
                  </span>
                </div>
              </div>
            ) : null}
          </>
        )
      ) : null}
    </section>
  );
}
