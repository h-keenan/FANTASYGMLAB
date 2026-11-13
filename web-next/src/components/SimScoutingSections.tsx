"use client";

import { StatGroup } from "@/components/PlayerQuickView";
import { ToneBadge } from "@/components/ToneBadge";
import { WeeklyPointsPanel } from "@/components/WeeklyPointsChartLazy";
import type { SimScoutingProfile } from "@/lib/simGame";
import {
  simCollegeCaption,
  simCollegeTiles,
  simCurveBand,
  simCurveCaption,
  simDraftLine,
  simMeasurableTiles,
  simOrdinal,
  simPercentileBand,
  simTagConfidenceLabel,
} from "@/lib/simScouting";


/**
 * The generated-prospect sections of the Fantasy Sim player sheet, in the real Player Quick View's own
 * section shell and tiles: scouting report (draft capital, tags, blurb), college production, measurables,
 * analytics percentiles vs the position class and the development curve. All of it is simulated and says so.
 */
export function SimScoutingSections({ profile }: { profile: SimScoutingProfile }) {
  const dev = profile.development;
  const real = profile.source !== "generated";
  return (
    <>
      <section className="pqv-stat-season" data-testid="sim-scouting-report">
        <div className="flex items-center justify-between gap-2 flex-wrap">
          <h3>Scouting report</h3>
          <span className="mb-2">
            <ToneBadge label={real ? "Prospect" : profile.label} color="var(--color-accent)" />
          </span>
        </div>
        <div className="pqv-signal-row">
          <span className="pqv-chip" title={profile.draft.basis}>
            {simDraftLine(profile.draft)} (proj.)
          </span>
          <span className="pqv-chip">Class rank #{profile.draft.class_rank} of {profile.draft.class_size}</span>
          {profile.tags.map((t) => (
            <span key={t.tag} className="pqv-chip" title={`${simTagConfidenceLabel(t.confidence)} confidence`}>
              {t.tag} · {simTagConfidenceLabel(t.confidence)}
            </span>
          ))}
        </div>
        <p className="text-sm pt-2" style={{ color: "var(--color-text-secondary)" }}>{profile.blurb}</p>
      </section>

      <section className="pqv-stat-season" data-testid="sim-college">
        <h3>College production</h3>
        <p className="pqv-status-text">{simCollegeCaption(profile.college)}</p>
        <StatGroup title="College production" items={simCollegeTiles(profile.college)} hideTitle />
      </section>

      <section className="pqv-stat-season" data-testid="sim-measurables">
        <h3>Measurables</h3>
        <StatGroup title="Measurables" items={simMeasurableTiles(profile)} hideTitle />
      </section>

      <section className="pqv-stat-season" data-testid="sim-analytics">
        <h3>Analytics vs position class</h3>
        <ul className="sim-pct-list">
          {profile.analytics.map((a) => (
            <li key={a.key} className="sim-pct-row" aria-label={`${a.label} ${a.display}, ${simOrdinal(a.percentile)} percentile`}>
              <span className="sim-pct-label">{a.label}</span>
              <span className="sim-pct-value">
                {a.display} · {simOrdinal(a.percentile)}
              </span>
              <span className="sim-pct-track" aria-hidden="true">
                <span className={`sim-pct-fill sim-pct-fill--${simPercentileBand(a.percentile)}`} style={{ width: `${a.percentile}%` }} />
              </span>
            </li>
          ))}
        </ul>
      </section>

      {dev.points.length > 0 ? (
        <section className="pqv-stat-season" data-testid="sim-dev-curve">
          <div className="flex items-center justify-between gap-2 flex-wrap">
            <h3>Development curve</h3>
            <span className="mb-2">
              <ToneBadge
                label={dev.revealed && dev.archetype_label ? dev.archetype_label : `Scouting ${dev.confidence_label.toLowerCase()} confidence`}
                color={dev.revealed ? "var(--color-success)" : "var(--color-warning)"}
              />
            </span>
          </div>
          <WeeklyPointsPanel
            name="Expected points per game"
            weeks={[]}
            season={0}
            projection={simCurveBand(dev)}
            pointsLabel="ppg"
            xLabel="Year"
            gradientId="sim-dev-fill"
          />
          <p className="pqv-status-text">
            <strong>{simCurveCaption(dev)}</strong> · {dev.note}
          </p>
        </section>
      ) : null}
    </>
  );
}
