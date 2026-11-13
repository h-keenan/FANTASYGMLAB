"use client";

import { useEffect, useState } from "react";

import { AccentCard } from "@/components/AccentCard";
import { Button } from "@/components/Button";
import { SimStandingsList } from "@/components/SimGameLeague";
import { SimGlyph } from "@/components/SimGlyph";
import { SimSectionTitle, SimToneBadge, type SimCtx } from "@/components/SimGameParts";
import { SkeletonRows } from "@/components/Skeleton";
import { ConfirmInPlace } from "@/components/ui/ConfirmInPlace";
import { Sheet } from "@/components/ui/Sheet";
import { api } from "@/lib/api";
import type { SimToOption, SimToResponse } from "@/lib/simGame";
import { simToCanForce, simToFixLabel, simToFixTab, simToHeadline, simToRecordLine, simToWeekLine } from "@/lib/simTo";

export interface SimToRequest {
  option: SimToOption;
  autoSet: boolean;
  forceFirst?: boolean;
}

/**
 * The "Sim to..." chooser: only the milestones that make sense for the stage the game is in (the server decides), and the
 * optional "auto-set my lineup each week" toggle (off by default). One tap runs the whole thing as a single request.
 */
export function SimToSheet({ ctx, open, onClose, onRun }: { ctx: SimCtx; open: boolean; onClose: () => void; onRun: (request: SimToRequest) => void }) {
  const [options, setOptions] = useState<SimToOption[] | null>(null);
  const [failed, setFailed] = useState(false);
  const [autoSet, setAutoSet] = useState(false);
  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    api
      .getSimToOptions(ctx.gameId)
      .then((body) => {
        if (cancelled) return;
        if (body.reason) setFailed(true);
        else {
          setFailed(false);
          setOptions(body.options ?? []);
        }
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [open, ctx.gameId, ctx.game.week, ctx.tick]);
  return (
    <Sheet open={open} onClose={onClose} title="Sim to..." description="Play several weeks at once. It stops early when you have something to decide.">
      <div className="flex flex-col gap-3" data-testid="sim-to-sheet">
        {failed ? (
          <p className="text-sm font-bold">Could not load the options. Try again in a moment.</p>
        ) : !options ? (
          <SkeletonRows count={3} />
        ) : options.length === 0 ? (
          <p className="text-sm">There is nothing to simulate right now.</p>
        ) : (
          <ul className="flex flex-col gap-2" aria-label="Sim to">
            {options.map((o) => (
              <li key={`${o.id}-${o.weeks ?? 0}`}>
                <Button className="w-full justify-start" variant="secondary" onClick={() => { onClose(); onRun({ option: o, autoSet }); }}>
                  <SimGlyph name="matchup" size={14} />
                  <span className="ml-2">{o.label}</span>
                </Button>
              </li>
            ))}
          </ul>
        )}
        <label className="flex items-start gap-2 text-sm" style={{ minHeight: "var(--touch-target-min)" }}>
          <input type="checkbox" className="mt-1" checked={autoSet} onChange={(event) => setAutoSet(event.target.checked)} aria-label="Auto-set my lineup each week" />
          <span>
            <strong>Auto-set my lineup each week</strong>
            <span className="block text-xs" style={{ color: "var(--color-text-muted)" }}>Plays your best healthy lineup before every week. Off: it stops when a starter is out or on a bye.</span>
          </span>
        </label>
      </div>
    </Sheet>
  );
}

/** The skipped weeks at a glance: record, rank, each result, injuries, claims, standings; the stop reason with its fix; undo. */
export function SimToResultView({
  result,
  onClose,
  onTab,
  onForce,
  onUndo,
  onGoPro,
}: {
  result: SimToResponse;
  onClose: () => void;
  onTab: (tab: "team" | "trades") => void;
  onForce: () => void;
  onUndo: () => Promise<boolean>;
  onGoPro: () => void;
}) {
  const played = result.weeks_played ?? 0;
  const s = result.summary;
  const stop = result.stopped ?? null;
  const fixLabel = stop ? simToFixLabel(stop) : null;
  return (
    <section className="flex flex-col gap-3" aria-label="Sim to summary" data-testid="sim-to-result">
      <SimSectionTitle glyph="matchup" tone="accent" note={s ? simToRecordLine(s) : undefined}>{simToHeadline(played, s)}</SimSectionTitle>
      {stop ? (
        <AccentCard accent="var(--color-warning)" compact as="div">
          <p className="text-sm font-extrabold" role="status" data-testid="sim-to-stop">{stop.message}</p>
          <div className="flex flex-wrap gap-2">
            {fixLabel ? (
              <Button
                size="sm"
                onClick={() => {
                  if (stop.fix === "premium") onGoPro();
                  else {
                    const tab = simToFixTab(stop);
                    if (tab) onTab(tab);
                    onClose();
                  }
                }}
              >
                {fixLabel}
              </Button>
            ) : null}
            {played === 0 && simToCanForce(stop) ? <Button size="sm" variant="secondary" onClick={onForce}>Sim anyway</Button> : null}
          </div>
        </AccentCard>
      ) : null}
      {s ? (
        <>
          <div className="grid grid-cols-3 gap-2" aria-label="Change">
            <Tile label="Record" value={s.record.after ?? "-"} />
            <Tile label="Rank" value={s.rank.after != null ? `#${s.rank.after}` : "-"} />
            <Tile label="Points" value={`+${s.pf.toFixed(1)}`} />
          </div>
          <ul className="flex flex-col gap-1" aria-label="Results">
            {s.weeks.map((w) => (
              <li key={w.week} className="flex items-center justify-between gap-2 text-sm" style={{ borderBottom: "var(--border-width-default) solid var(--color-border)", minHeight: 36 }}>
                <span className="flex items-center gap-2">
                  <SimToneBadge label={w.kind === "playoff" ? `Rd ${w.round ?? ""}`.trim() : `Wk ${w.week}`} tone="muted" />
                  <span className="font-bold" style={{ color: w.result === "w" ? "var(--color-success)" : w.result === "l" ? "var(--color-danger)" : undefined }}>{simToWeekLine(w)}</span>
                </span>
                {w.auto_filled.length > 0 ? <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>auto-filled {w.auto_filled.join(", ")}</span> : null}
              </li>
            ))}
          </ul>
          {s.injuries.length > 0 ? (
            <AccentCard accent="var(--color-danger)" compact as="div">
              <p className="text-xs font-extrabold">Injuries to your team</p>
              <ul className="text-sm">{s.injuries.map((i, k) => <li key={k}>Week {i.week}: {i.player.name} ({i.player.pos}), out {i.weeks} week{i.weeks === 1 ? "" : "s"}</li>)}</ul>
            </AccentCard>
          ) : null}
          {s.claims.length > 0 ? (
            <AccentCard accent="var(--color-accent)" compact as="div">
              <p className="text-xs font-extrabold">Waiver claims</p>
              <ul className="text-sm">{s.claims.map((c, k) => <li key={k}>Week {c.week}: {c.ok === false ? "missed" : "added"} {c.add?.name ?? "a player"}{c.drop ? `, dropped ${c.drop.name}` : ""}</li>)}</ul>
            </AccentCard>
          ) : null}
          {s.ai_trades > 0 ? <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>{s.ai_trades} trade{s.ai_trades === 1 ? "" : "s"} around the league. See the Feed for who moved.</p> : null}
          {s.champion ? <p className="text-sm font-bold">The season is over. {s.standings.find((r) => r.team_id === s.champion)?.name ?? "A team"} are the champions.</p> : null}
          <SimStandingsList rows={s.standings} />
        </>
      ) : null}
      <div className="flex flex-wrap items-center gap-2">
        <Button onClick={onClose}>Continue</Button>
        {played > 0 && result.from_seq != null ? <ConfirmInPlace label="Undo this sim" buttonVariant="secondary" size="sm" onConfirm={onUndo} /> : null}
      </div>
    </section>
  );
}

function Tile({ label, value }: { label: string; value: string }) {
  return (
    <div className="glass-surface flex flex-col items-center px-1 py-1.5">
      <span className="text-[0.6875rem]" style={{ color: "var(--color-text-muted)" }}>{label}</span>
      <span className="text-sm font-extrabold tabular-nums">{value}</span>
    </div>
  );
}
