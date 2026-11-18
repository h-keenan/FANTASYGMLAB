"use client";

import { useState, type ReactNode } from "react";

import { ButtonLink } from "@/components/Button";
import { ExchangeSide } from "@/components/TradeAssetExchange";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { ToneBadge } from "@/components/ToneBadge";
import { CompactModule } from "@/components/ui/CompactModule";
import { Collapse } from "@/components/ui/Presence";
import { type GmPlanOutlookItem, type GmPlanTradeItem, type TradeAsset } from "@/lib/api";
import { abbreviatePlayerName } from "@/lib/formatPlayerName";
import type { PlanStep } from "@/lib/gmPlanPlan";
import { deltaBand } from "@/lib/verdictTone";
import { tradeIdeaGainPhrase, tradeIdeaNamesText } from "@/lib/tradeIdeaSummary";

const CHIP_COLOR = { accent: "var(--color-accent)", success: "var(--color-success)", muted: "var(--color-text-muted)" } as const;

type Person = { id: string | null; name: string; position?: string; team?: string };

function players(assets: TradeAsset[], fallbackId: string, fallbackName: string): Person[] {
  const found = assets.filter((a) => a.asset_type === "player" && a.name).map((a) => ({ id: a.player_id ?? null, name: a.name!, position: a.position, team: a.team }));
  return found.length > 0 ? found : fallbackName ? [{ id: fallbackId || null, name: fallbackName }] : [];
}

export function Avatars({ people, size = 28 }: { people: Person[]; size?: number }) {
  return (
    <span className="flex shrink-0 items-center">
      {people.map((p, i) => (
        <span key={`${p.id ?? p.name}-${i}`} style={{ marginLeft: i === 0 ? 0 : -8 }}>
          <PlayerAvatar playerId={p.id} name={p.name} position={p.position} team={p.team} size={size} />
        </span>
      ))}
    </span>
  );
}

/** The avatars a trade item stands for: the first player each way. */
export function tradeAvatarPeople(item: GmPlanTradeItem): Person[] {
  return [...players(item.send_assets, item.my_player_id, item.my_player).slice(0, 1), ...players(item.receive_assets, item.their_player_id, item.their_player).slice(0, 1)];
}

/** One trade idea inside a step: a compact row that opens on tap. Not a card; the step around it is the only card. */
function TradeRow({ item, detailsHref }: { item: GmPlanTradeItem; detailsHref?: string }) {
  const [open, setOpen] = useState(false);
  const gain = item.trade_gain;
  const sendNames = players(item.send_assets, item.my_player_id, item.my_player).map((p) => abbreviatePlayerName(p.name));
  const getNames = players(item.receive_assets, item.their_player_id, item.their_player).map((p) => abbreviatePlayerName(p.name));
  const gainColor = gain != null && deltaBand(gain) === "good" ? "var(--color-success)" : "var(--color-text-muted)";
  return (
    <div style={{ borderTop: "var(--border-width-default) solid var(--color-border)" }} data-testid="plan-trade-row">
      <button
        type="button"
        aria-expanded={open}
        aria-label={`${item.partner_team_name || "Trade idea"}: ${tradeIdeaNamesText(sendNames)} for ${tradeIdeaNamesText(getNames)}`}
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-3 py-2 text-left"
        style={{ minHeight: "var(--touch-target-min)" }}
      >
        <Avatars people={tradeAvatarPeople(item)} />
        <span className="flex min-w-0 flex-1 flex-col gap-1">
          <span className="text-[0.6875rem] font-extrabold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
            {item.partner_team_name || "Trade idea"}
          </span>
          <span className="break-words text-sm font-semibold">
            {tradeIdeaNamesText(sendNames)} for {tradeIdeaNamesText(getNames)}
          </span>
          <span className="flex flex-wrap items-center gap-1">
            {gain != null ? <ToneBadge size="xs" label={tradeIdeaGainPhrase(gain)} color={gainColor} /> : null}
            {item.trade_confidence_label ? <ToneBadge size="xs" label={item.trade_confidence_label} color="var(--color-accent)" title={`${item.trade_confidence_label} confidence`} /> : null}
          </span>
        </span>
        <svg aria-hidden="true" width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round" className="shrink-0" style={{ color: "var(--color-text-muted)", transform: open ? "rotate(180deg)" : "none" }}>
          <path d="m6 9 6 6 6-6" />
        </svg>
      </button>
      <Collapse open={open}>
        <div className="flex flex-col gap-2 pb-2">
          <div className="grid grid-cols-1 gap-2">
            <ExchangeSide label="You send" dotColor="var(--color-text-muted)" assets={item.send_assets} />
            <ExchangeSide label="You get" dotColor="var(--color-success)" assets={item.receive_assets} />
          </div>
          <div className="flex items-end justify-between gap-3">
            <p className="min-w-0 flex-1 text-xs" style={{ color: "var(--color-text-secondary)" }}>{item.rationale || item.trade_confidence_label}</p>
            {detailsHref ? (
              <ButtonLink href={detailsHref} variant="accentOutline" size="sm" className="shrink-0">
                View details
              </ButtonLink>
            ) : null}
          </div>
        </div>
      </Collapse>
    </div>
  );
}

const OUTLOOK_TONE = { success: "var(--color-success)", muted: "var(--color-text-muted)", accent: "var(--color-accent)" } as const;

/** One Team Outlook fact (handshake item 7): avatars, the label and headline, and the reasons behind it on tap. */
export function OutlookRow({ item }: { item: GmPlanOutlookItem }) {
  const [open, setOpen] = useState(false);
  const people = item.players.map((p) => ({ id: p.player_id || null, name: p.name, position: p.position, team: p.team }));
  return (
    <div style={{ borderTop: "var(--border-width-default) solid var(--color-border)" }} data-testid="plan-outlook-row" data-topic={item.outlook_topic}>
      <button
        type="button"
        aria-expanded={open}
        aria-label={`${item.label}: ${item.headline}`}
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-3 py-2 text-left"
        style={{ minHeight: "var(--touch-target-min)" }}
      >
        {people.length > 0 ? <Avatars people={people} /> : null}
        <span className="flex min-w-0 flex-1 flex-col gap-1">
          <span className="text-[0.6875rem] font-extrabold uppercase" style={{ color: OUTLOOK_TONE[item.tone] ?? OUTLOOK_TONE.accent, letterSpacing: "var(--letter-spacing-badge)" }}>
            {item.label}
          </span>
          <span className="break-words text-sm font-semibold">{item.headline}</span>
        </span>
        <svg aria-hidden="true" width={14} height={14} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.4} strokeLinecap="round" strokeLinejoin="round" className="shrink-0" style={{ color: "var(--color-text-muted)", transform: open ? "rotate(180deg)" : "none" }}>
          <path d="m6 9 6 6 6-6" />
        </svg>
      </button>
      <Collapse open={open}>
        <ul className="list-disc pb-2 pl-5 text-xs" style={{ color: "var(--color-text-secondary)" }}>
          {item.why.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      </Collapse>
    </div>
  );
}

function StepNumber({ n }: { n: number }) {
  return (
    <span className="inline-flex h-5 w-5 shrink-0 items-center justify-center text-[0.6875rem] font-extrabold" style={{ borderRadius: "var(--radius-pill)", background: "color-mix(in srgb, var(--color-accent) 18%, transparent)", color: "var(--color-accent)" }}>
      {n}
    </span>
  );
}

/** The numbered action steps (GM Plan Overview, concept C). The trades step nests its ideas; an area step nests that area's items. */
export function PlanSteps({
  steps,
  tradeItems,
  detailsHref,
  renderArea,
  tradeEmpty,
}: {
  steps: PlanStep[];
  tradeItems: GmPlanTradeItem[];
  detailsHref?: (item: GmPlanTradeItem) => string;
  renderArea: (areaKey: string) => ReactNode;
  /** Shown inside the trades step when there are no trade ideas. */
  tradeEmpty?: ReactNode;
}) {
  return (
    <>
      {steps.map((step, i) => {
        const body = step.kind === "trades" ? (tradeItems.length === 0 ? tradeEmpty : (
          <div className="-mt-2 flex flex-col">
            {tradeItems.map((item, idx) => (
              <TradeRow key={`${item.my_player_id}-${item.their_player_id}-${idx}`} item={item} detailsHref={detailsHref?.(item)} />
            ))}
          </div>
        )) : step.kind === "area" && step.areaKey ? renderArea(step.areaKey) : undefined;
        return (
          <CompactModule
            key={step.key}
            id={`gmplan.step.${step.key}`}
            persist={false}
            defaultOpen={i === 0 && step.kind === "trades"}
            testId={`plan-step-${step.key}`}
            title={<span className="flex items-center gap-2"><StepNumber n={i + 1} />{step.title}</span>}
            label={step.title}
            parts={[{ key: "s", text: step.summary }]}
            action={step.chip ? <ToneBadge size="xs" label={step.chip.label} color={CHIP_COLOR[step.chip.tone]} /> : undefined}
            preview={step.kind === "trades" && tradeItems.length > 0 ? <div className="pt-1"><Avatars people={tradeItems.slice(0, 3).flatMap((t) => tradeAvatarPeople(t).slice(1))} /></div> : undefined}
          >
            {body}
          </CompactModule>
        );
      })}
    </>
  );
}
