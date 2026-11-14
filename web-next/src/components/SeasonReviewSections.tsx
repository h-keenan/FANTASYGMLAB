"use client";

import { TrendChart } from "@/components/ui/TrendChart";
import type { ReactNode } from "react";

import { AccentCard } from "@/components/AccentCard";
import { PositionBadge } from "@/components/PositionBadge";
import { SectionHeading } from "@/components/SectionHeading";
import { ReviewGlyphIcon } from "@/components/SimReviewGlyph";
import { CompactModule } from "@/components/ui/CompactModule";
import { RecapCard } from "@/components/ui/RecapCard";
import { RECAP_CARD_ROWS, recapCardModel } from "@/lib/recapCard";
import { SimPlayerChip as BaseChip, simToneColor, useSimWide } from "@/components/SimGameParts";
import { ToneBadge } from "@/components/ToneBadge";
import type { SimPlayerRef } from "@/lib/simGame";
import { reviewSectionParts } from "@/lib/simReview";
import type {
  ReviewCard,
  ReviewGameRow,
  ReviewGlyph,
  ReviewLeaderGroup,
  ReviewPathStep,
  ReviewPlayer,
  ReviewSection,
  ReviewStat,
  ReviewTone,
} from "@/lib/simReview";

/**
 * The data-driven Season in Review body: renders a typed `ReviewSection[]`.
 * The sim's final grade page feeds it from `buildSimReviewSections`; the real
 * league yearly summary will map its own data into the same list. Colors are
 * semantic tokens only; every box has a fixed or content-driven size that does
 * not depend on a photo loading.
 */

/** A review player is the sim brief shape; `pos` is a plain string here so real-league data can feed it. */
function SimPlayerChip({ player, size, className, hidePosition }: { player: ReviewPlayer; size?: number; className?: string; hidePosition?: boolean }) {
  return <BaseChip player={player as unknown as SimPlayerRef} size={size} className={className} hidePosition={hidePosition} />;
}

const ROLE_BADGE: Record<string, { label: string; tone: ReviewTone }> = {
  get: { label: "Got", tone: "success" },
  give: { label: "Sent", tone: "danger" },
  add: { label: "Added", tone: "success" },
  drop: { label: "Dropped", tone: "danger" },
  pick: { label: "Pick", tone: "accent" },
  hurt: { label: "Hurt", tone: "danger" },
  bench: { label: "Benched", tone: "warning" },
  started: { label: "Started", tone: "muted" },
  boom: { label: "Boom", tone: "success" },
  bust: { label: "Bust", tone: "danger" },
};

export function ReviewGlyphChip({ glyph, tone, size = 28 }: { glyph: ReviewGlyph; tone: ReviewTone; size?: number }) {
  const color = simToneColor(tone);
  return (
    <span
      aria-hidden="true"
      className="inline-flex shrink-0 items-center justify-center"
      style={{ width: size, height: size, borderRadius: "var(--radius-pill)", color, background: `color-mix(in srgb, ${color} var(--chip-fill-pct, 15%), transparent)` }}
    >
      <ReviewGlyphIcon glyph={glyph} size={Math.round(size * 0.58)} />
    </span>
  );
}

export function ReviewDeltaText({ text, tone, size = "lg" }: { text: string; tone: ReviewTone; size?: "lg" | "sm" }) {
  return (
    <span className={`${size === "lg" ? "text-lg" : "text-sm"} font-extrabold whitespace-nowrap tabular-nums`} style={{ color: simToneColor(tone) }}>
      {text}
    </span>
  );
}

function PlayerLine({ player, showRole }: { player: ReviewPlayer; showRole: boolean }) {
  const role = showRole && player.role ? ROLE_BADGE[player.role] : undefined;
  return (
    <div className="flex items-center justify-between gap-2 min-w-0">
      <SimPlayerChip player={player} className="min-w-0 flex-1" />
      {role ? (
        <span className="shrink-0" style={{ minWidth: "4.5rem", textAlign: "right" }}>
          <ToneBadge label={role.label} color={simToneColor(role.tone)} size="xs" />
        </span>
      ) : null}
    </div>
  );
}

export function ReviewCardView({ card }: { card: ReviewCard }) {
  const color = simToneColor(card.tone);
  return (
    <AccentCard accent={color} compact as="div" data-testid="review-card">
      <div className="flex flex-wrap items-start gap-2">
        <ReviewGlyphChip glyph={card.glyph} tone={card.tone} />
        <div className="flex min-w-[9rem] flex-1 flex-col">
          <span className="text-xs uppercase font-extrabold" style={{ color, letterSpacing: "var(--letter-spacing-badge)" }}>{card.label}</span>
          <p className="text-sm font-bold break-words">{card.headline}</p>
        </div>
        <div className="ml-auto flex shrink-0 flex-col items-end gap-1">
          {card.delta ? <ReviewDeltaText text={card.delta.text} tone={card.delta.tone} /> : null}
          {card.chip ? <ToneBadge label={card.chip.label} color={simToneColor(card.chip.tone)} size="xs" /> : null}
        </div>
      </div>
      {card.players.length > 0 ? (
        <div className="flex flex-col gap-1 py-1">
          {card.players.slice(0, 4).map((p, i) => <PlayerLine key={`${p.id}-${i}`} player={p} showRole={card.players.length > 1} />)}
        </div>
      ) : null}
      {card.detail ? <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>{card.detail}</p> : null}
    </AccentCard>
  );
}

/** The stats as recap cards: three label/value rows per card (7b V2), every stat kept, a player chip under its row. */
function ReviewStatCards({ section }: { section: Extract<ReviewSection, { kind: "stats" }> }) {
  const groups: ReviewStat[][] = [];
  for (let i = 0; i < section.items.length; i += RECAP_CARD_ROWS) groups.push(section.items.slice(i, i + RECAP_CARD_ROWS));
  return (
    <div className="grid grid-cols-1 gap-2 md:grid-cols-2" data-testid="review-stat-cards">
      {groups.map((group, g) => {
        const rows = group.map((s, i) => ({ key: `${g}-${i}`, label: s.label, value: s.value, sub: s.sub ?? null, tone: s.tone }));
        const extras = Object.fromEntries(group.map((s, i) => [`${g}-${i}`, s.player ? <SimPlayerChip key={i} player={s.player} size={28} /> : null]));
        return <RecapCard key={g} model={recapCardModel({ kicker: g === 0 ? section.title : `${section.title} (${g + 1})`, rows })} extras={extras} testId="review-stat" />;
      })}
    </div>
  );
}

const STEP_TONE: Record<ReviewPathStep["result"], ReviewTone> = { win: "success", loss: "danger", bye: "warning" };

function PathView({ steps, caption }: { steps: ReviewPathStep[]; caption?: string }) {
  return (
    <div className="flex flex-col gap-2">
      {caption ? <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>{caption}</p> : null}
      <ol className="flex flex-col" data-testid="review-path">
        {steps.map((s, i) => {
          const tone = STEP_TONE[s.result];
          const color = simToneColor(tone);
          return (
            <li key={i} className="flex items-stretch gap-3">
              <div className="flex w-7 shrink-0 flex-col items-center">
                <ReviewGlyphChip glyph={s.result === "win" ? "trophy" : s.result === "bye" ? "path" : "bust"} tone={tone} size={28} />
                {i < steps.length - 1 ? <span className="w-0.5 flex-1" style={{ background: "var(--color-border-strong)", minHeight: "0.75rem" }} /> : null}
              </div>
              <div className="flex min-w-0 flex-1 items-start justify-between gap-2 pb-3">
                <div className="min-w-0">
                  <p className="text-sm font-bold">{s.label}</p>
                  {s.sub ? <p className="text-xs break-words" style={{ color: "var(--color-text-secondary)" }}>{s.sub}</p> : null}
                </div>
                <div className="flex shrink-0 flex-col items-end gap-1">
                  {s.score ? <span className="text-sm font-extrabold tabular-nums" style={{ color }}>{s.score}</span> : null}
                  <ToneBadge label={s.result === "win" ? "Won" : s.result === "loss" ? "Lost" : "Bye"} color={color} size="xs" />
                </div>
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}

function JourneyView({ points, teams }: { points: { label: string; rank: number; sub?: string }[]; teams: number }) {
  const best = Math.min(...points.map((p) => p.rank));
  const worst = Math.max(...points.map((p) => p.rank));
  const last = points[points.length - 1];
  return (
    <div className="glass-surface flex flex-col gap-2 p-3" data-testid="review-journey">
      <TrendChart
        points={points.map((p, i) => ({ x: i, y: p.rank, label: `${p.label} · ${p.sub ?? ""}`.replace(/ · $/, "") }))}
        name="Standings rank by week"
        unit="rank"
        xNoun="week"
        formatX={(i) => points[Math.round(i)]?.label ?? ""}
        formatY={(v) => `#${Math.round(v)}`}
        yDomain={[1, Math.max(2, teams)]}
        invertY
        height={120}
        pointColor={(pt) => (pt.y === best ? "var(--color-success)" : pt.y === worst ? "var(--color-danger)" : undefined)}
        testId="review-journey-chart"
      />
      <div className="flex items-center justify-between text-xs" style={{ color: "var(--color-text-muted)" }}>
        <span>{points[0].label}: #{points[0].rank}</span>
        <span><span style={{ color: "var(--color-success)" }}>Peak #{best}</span> · <span style={{ color: "var(--color-danger)" }}>Low #{worst}</span></span>
        <span>{last.label}: #{last.rank}</span>
      </div>
    </div>
  );
}

function LeaderGroup({ group }: { group: ReviewLeaderGroup }) {
  return (
    <div className="glass-surface flex min-w-0 flex-col gap-1 p-3" data-testid="review-leaders">
      <div className="flex items-center gap-2">
        {group.pos ? <span className="w-11 shrink-0"><PositionBadge position={group.pos} /></span> : null}
        <span className="text-xs uppercase font-extrabold" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
          {group.pos ? "Leaders" : group.title}
        </span>
      </div>
      {group.rows.map((r, i) => (
        <div key={`${r.player.id}-${i}`} className="flex items-center gap-2" style={{ borderTop: i ? "var(--border-width-default) solid var(--color-border)" : undefined, paddingTop: i ? "0.25rem" : 0 }}>
          <span className="w-4 shrink-0 text-xs font-extrabold tabular-nums" style={{ color: i === 0 ? "var(--color-premium, var(--color-warning))" : "var(--color-text-muted)" }}>{i + 1}</span>
          <SimPlayerChip player={r.player} size={28} className="min-w-0 flex-1" hidePosition={Boolean(group.pos)} />
          <div className="flex shrink-0 flex-col items-end leading-tight">
            <span className="text-sm font-extrabold tabular-nums" style={{ color: r.highlight ? "var(--color-accent)" : "var(--color-text-primary)" }}>{r.value}</span>
            {r.sub ? <span className="text-xs max-w-[11rem] truncate" style={{ color: "var(--color-text-muted)" }}>{r.sub}</span> : null}
          </div>
        </div>
      ))}
    </div>
  );
}

function GameRow({ row }: { row: ReviewGameRow }) {
  const color = row.tone === "muted" ? "var(--color-border-strong)" : simToneColor(row.tone);
  return (
    <AccentCard accent={color} compact as="div">
      <div className="flex items-center justify-between gap-2">
        <p className="min-w-0 text-sm font-semibold break-words">{row.label}</p>
        <span className="shrink-0 text-sm font-extrabold tabular-nums">{row.score}</span>
      </div>
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>{row.sub}</p>
        {row.chip ? <ToneBadge label={row.chip.label} color={simToneColor(row.chip.tone)} size="xs" /> : null}
      </div>
    </AccentCard>
  );
}

/** Phone: swipeable snap cards (one screen of height, not a tall stack); md and up: the original grid. */
const CAROUSEL = "-mx-1 flex snap-x gap-2 overflow-x-auto px-1 pb-1 md:mx-0 md:grid md:grid-cols-2 md:overflow-visible md:px-0 md:pb-0";
const CAROUSEL_ITEM = "flex w-[84%] shrink-0 snap-start flex-col md:w-auto [&>*]:flex-1";

function SectionBody({ section }: { section: ReviewSection }): ReactNode {
  switch (section.kind) {
    case "stats":
      return <ReviewStatCards section={section} />;
    case "cards":
      return <div className={CAROUSEL}>{section.cards.map((c) => <div key={c.id} className={CAROUSEL_ITEM}><ReviewCardView card={c} /></div>)}</div>;
    case "path":
      return <PathView steps={section.steps} caption={section.caption} />;
    case "journey":
      return <JourneyView points={section.points} teams={section.teams} />;
    case "leaders":
      return <div className={CAROUSEL}>{section.groups.map((g, i) => <div key={`${g.title}-${i}`} className={CAROUSEL_ITEM}><LeaderGroup group={g} /></div>)}</div>;
    case "games":
      return <div className="flex flex-col gap-2">{section.rows.map((r, i) => <GameRow key={i} row={r} />)}</div>;
  }
}

export function SeasonReviewSections({
  sections,
  only,
  closed = [],
}: {
  sections: readonly ReviewSection[];
  /** Render just these section ids (a Season in Review tab). */
  only?: readonly string[];
  /** Section ids that start collapsed on a phone. */
  closed?: readonly string[];
}) {
  const wide = useSimWide();
  const list = only ? sections.filter((s) => only.includes(s.id)) : sections;
  return (
    <>
      {list.map((section) =>
        wide ? (
          <section key={section.id} className="flex flex-col gap-2" aria-label={section.title} data-testid={`review-section-${section.id}`}>
            <SectionHeading note={section.note} size="compact">
              <span className="inline-flex items-center gap-2">
                <ReviewGlyphChip glyph={section.glyph} tone="accent" size={24} />
                {section.title}
              </span>
            </SectionHeading>
            <SectionBody section={section} />
          </section>
        ) : (
          <CompactModule
            key={section.id}
            id={`review.${section.id}`}
            testId={`review-section-${section.id}`}
            defaultOpen={!closed.includes(section.id)}
            title={
              <span className="inline-flex items-center gap-2">
                <ReviewGlyphChip glyph={section.glyph} tone="accent" size={22} />
                {section.title}
              </span>
            }
            label={section.title}
            parts={reviewSectionParts(section)}
          >
            {section.note ? <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>{section.note}</p> : null}
            <SectionBody section={section} />
          </CompactModule>
        ),
      )}
    </>
  );
}
