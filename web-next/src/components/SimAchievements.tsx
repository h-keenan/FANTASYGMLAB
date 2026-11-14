"use client";

import { useState, type CSSProperties } from "react";

import { AccentCard } from "@/components/AccentCard";
import { SimFold } from "@/components/SimGameParts";
import { SimGlyph } from "@/components/SimGlyph";
import { ToneBadge } from "@/components/ToneBadge";
import { TrophyIcon } from "@/components/TrophyIcon";
import {
  simAchievementColor,
  simAchievementDate,
  simAchievementGlyph,
  simAchievementGroups,
  simAchievementLine,
  simAchievementProgressPct,
  simAchievementRarityLabel,
  simAchievementsParts,
  type SimAchievement,
  type SimAchievementsPayload,
  type SimTrophyRow,
} from "@/lib/simAchievements";

/** The round badge: a rarity-coloured ring around the glyph (muted and dashed while locked). Decorative; the row carries the name. */
export function SimAchievementBadge({ a, size = 36 }: { a: Pick<SimAchievement, "icon" | "rarity" | "tone" | "unlocked">; size?: number }) {
  const color = simAchievementColor(a);
  const style: CSSProperties = {
    width: size,
    height: size,
    borderRadius: "var(--radius-pill)",
    color,
    background: a.unlocked ? `color-mix(in srgb, ${color} 14%, transparent)` : "transparent",
    boxShadow: `inset 0 0 0 2px color-mix(in srgb, ${color} ${a.unlocked ? 70 : 35}%, transparent)`,
    opacity: a.unlocked ? 1 : 0.8,
  };
  return (
    <span className="inline-flex shrink-0 items-center justify-center" style={style} aria-hidden="true" data-testid="achievement-badge" data-rarity={a.rarity} data-unlocked={a.unlocked ? "true" : "false"}>
      <SimGlyph name={simAchievementGlyph(a.icon)} size={Math.round(size * 0.5)} />
    </span>
  );
}

/** One badge row: tap to open its detail (what it is, when, how far along). */
function Row({ a }: { a: SimAchievement }) {
  const [open, setOpen] = useState(false);
  const color = simAchievementColor(a);
  const date = simAchievementDate(a);
  const pct = simAchievementProgressPct(a.progress);
  return (
    <li>
      <button
        type="button"
        className="flex w-full items-center gap-3 py-2 text-left"
        style={{ minHeight: "var(--touch-target-min)" }}
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        data-testid="achievement-row"
        data-unlocked={a.unlocked ? "true" : "false"}
      >
        <SimAchievementBadge a={a} />
        <span className="flex min-w-0 flex-1 flex-col">
          <span className="break-words text-sm font-extrabold" style={{ color: a.unlocked ? "var(--color-text-primary)" : "var(--color-text-secondary)" }}>{a.name}</span>
          <span className="truncate text-xs" style={{ color: "var(--color-text-muted)" }}>
            {a.unlocked ? date : a.progress ? a.progress.text : "Locked"}
          </span>
        </span>
        <ToneBadge label={simAchievementRarityLabel(a.rarity)} color={a.unlocked ? color : "var(--color-text-muted)"} size="xs" />
      </button>
      {!a.unlocked && a.progress ? (
        <div className="mb-1 ml-12 h-1 overflow-hidden" style={{ borderRadius: "var(--radius-pill)", background: "var(--color-surface-muted)" }} role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label={`${a.name} progress`}>
          <div style={{ width: `${pct}%`, height: "100%", background: color, opacity: 0.8 }} />
        </div>
      ) : null}
      {open ? (
        <p className="mb-2 ml-12 text-xs" style={{ color: "var(--color-text-secondary)" }} data-testid="achievement-detail">
          {simAchievementLine(a)}
          {a.unlocked && a.player ? ` (${a.player.name})` : ""}
        </p>
      ) : null}
    </li>
  );
}

/**
 * The Achievements CompactModule (Home, the offseason review and the final Season in Review): the badges earned this season,
 * the career ladder and what is still locked with progress. Renders only what the server's `achievements` payload says.
 */
export function SimAchievementsModule({ payload, seasonNo, id = "home.achievements", openOnPhone = false }: { payload: SimAchievementsPayload | null | undefined; seasonNo?: number | null; id?: string; openOnPhone?: boolean }) {
  if (!payload || !Array.isArray(payload.items)) return null;
  const groups = simAchievementGroups(payload, seasonNo);
  return (
    <SimFold id={id} glyph="trophy" tone="warning" title="Achievements" parts={simAchievementsParts(payload)} openOnPhone={openOnPhone} testId="sim-achievements">
      {groups.length === 0 ? (
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>Nothing earned yet. Win a few, stack a streak, chase a title.</p>
      ) : (
        <div className="flex flex-col gap-3">
          {groups.map((g) => (
            <section key={`${g.key}-${g.title}`} aria-label={g.title}>
              <p className="text-xs font-extrabold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>{g.title}</p>
              <ul>{g.items.map((a) => <Row key={a.id} a={a} />)}</ul>
            </section>
          ))}
        </div>
      )}
    </SimFold>
  );
}

/** A team's champion trophies, newest first (team history). Gold: a title is the premium meaning here. */
export function SimTrophyRow({ rows }: { rows: SimTrophyRow[] }) {
  if (rows.length === 0) return null;
  return (
    <section className="flex flex-col gap-2" aria-label="Championship trophies" data-testid="sim-trophy-row">
      <ul className="flex flex-wrap gap-2">
        {rows.map((r) => (
          <li key={r.label}>
            <AccentCard accent="var(--color-premium)" compact as="div">
              <div className="flex items-center gap-2">
                <TrophyIcon size={28} color="var(--color-premium)" />
                <span className="flex flex-col">
                  <span className="text-sm font-extrabold">{r.label}</span>
                  <span className="text-xs tabular-nums" style={{ color: "var(--color-text-secondary)" }}>{r.record}</span>
                </span>
              </div>
            </AccentCard>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** Compact badge chips (your team page, a player's History tab). */
export function SimBadgeChips({ items, label = "Achievements" }: { items: SimAchievement[]; label?: string }) {
  if (items.length === 0) return null;
  return (
    <ul className="flex flex-wrap gap-2" aria-label={label} data-testid="sim-badge-chips">
      {items.map((a) => (
        <li key={a.id} className="inline-flex items-center gap-2 pr-2" style={{ borderRadius: "var(--radius-pill)", background: "var(--color-surface-muted)" }} title={a.detail}>
          <SimAchievementBadge a={a} size={28} />
          <span className="text-xs font-bold">{a.name}<span style={{ color: "var(--color-text-muted)" }}> {a.season_label}</span></span>
        </li>
      ))}
    </ul>
  );
}
