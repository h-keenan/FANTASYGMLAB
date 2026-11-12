"use client";

import { useCallback, useEffect, useState } from "react";

import { AccentCard } from "@/components/AccentCard";
import { Button, ButtonLink } from "@/components/Button";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { PageTitle } from "@/components/PageTitle";
import { PremiumUpsellCard } from "@/components/PremiumUpsellCard";
import { SectionHeading } from "@/components/SectionHeading";
import { SkeletonCard } from "@/components/Skeleton";
import { ToneBadge } from "@/components/ToneBadge";
import { api } from "@/lib/api";
import {
  SIM_DISCLAIMER,
  SIM_GAME_CARD,
  SIM_LABEL,
  isSimOffError,
  simFactorImpact,
  simFactorKindLabel,
  simFactorsIntro,
  simFinishRange,
  simFormatCurrent,
  simFormatPercent,
  simGate,
  simHeadline,
  simNoteMessages,
  simOddsTone,
  simOrdinal,
  simReasonMessage,
  simScopeLine,
  simUnavailableCopy,
  simWinsRange,
  type SimForecastResponse,
  type SimTone,
  type SimUnavailableCause,
  type SimUpsell,
} from "@/lib/simPresentation";

type Phase =
  | { kind: "loading" }
  | { kind: "unavailable"; cause: SimUnavailableCause }
  | { kind: "premium"; upsell: SimUpsell | null }
  | { kind: "notice"; message: string }
  | { kind: "ready"; data: SimForecastResponse }
  | { kind: "error"; message: string };

const TONE_COLOR: Record<SimTone, string> = {
  success: "var(--color-success)",
  accent: "var(--color-accent)",
  warning: "var(--color-warning)",
  danger: "var(--color-danger)",
};

function errorText(error: unknown, fallback: string): string {
  if (typeof error === "object" && error !== null) {
    const e = error as { status?: number; code?: string; message?: string };
    if (e.status === 503 || e.code === "server_busy") return "The forecast is busy right now. Try again in a few seconds.";
    if (e.message) return e.message;
  }
  return fallback;
}

function SimBanner({ scope }: { scope: string }) {
  return (
    <div role="note" className="flex flex-col gap-1 text-xs" style={{ color: "var(--color-text-secondary)" }}>
      <span className="flex items-center gap-2">
        <ToneBadge label={SIM_LABEL} color="var(--color-accent)" size="xs" />
        <span className="font-semibold">{scope}</span>
      </span>
      <span>{SIM_DISCLAIMER}</span>
    </div>
  );
}

function ForecastSkeleton() {
  return (
    <div className="flex flex-col gap-4" role="status" aria-label="Building your forecast">
      <SkeletonCard lines={4} />
      <SkeletonCard lines={3} />
      <SkeletonCard lines={5} />
    </div>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <main className="flex-1 flex flex-col gap-5 px-4 py-6 max-w-3xl w-full mx-auto">
      <PageTitle page="Season Outlook" />
      {children}
    </main>
  );
}

export function FantasySimContent({ leagueId, leagueName }: { leagueId: string; leagueName: string }) {
  const [phase, setPhase] = useState<Phase>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    api
      .getSimForecast(leagueId)
      .then((data) => {
        if (cancelled) return;
        const gate = simGate(data);
        if (gate.kind === "premium") return setPhase({ kind: "premium", upsell: gate.upsell });
        if (gate.kind === "unavailable") return setPhase({ kind: "unavailable", cause: gate.cause });
        if (data.reason || !data.forecast) {
          return setPhase({ kind: "notice", message: simReasonMessage(data.reason) || "We could not build your forecast. Try again." });
        }
        setPhase({ kind: "ready", data });
      })
      .catch((error) => {
        if (cancelled) return;
        if (isSimOffError(error)) setPhase({ kind: "unavailable", cause: "off" });
        else setPhase({ kind: "error", message: errorText(error, "Could not build your season outlook.") });
      });
    return () => {
      cancelled = true;
    };
  }, [leagueId, attempt]);

  const refresh = useCallback(() => {
    setPhase({ kind: "loading" });
    setAttempt((n) => n + 1);
  }, []);

  if (phase.kind === "loading") {
    return (
      <Shell>
        <p className="text-sm font-semibold" role="status">
          Playing out the rest of your season…
        </p>
        <ForecastSkeleton />
      </Shell>
    );
  }
  if (phase.kind === "error") return <ErrorState message={phase.message} onRetry={refresh} />;
  if (phase.kind === "premium") {
    return (
      <PremiumUpsellCard
        kicker="Season Outlook"
        leagueName={leagueName}
        upsell={phase.upsell}
        fallbackTitle="See your season forecast"
        fallbackBody="Season Outlook is a Pro feature in your GM Plan: one tap shows your playoff odds, projected record and finish, title odds, and the moves and games that swing your season. Start your free trial to unlock it."
      />
    );
  }
  if (phase.kind === "unavailable") {
    const copy = simUnavailableCopy();
    return (
      <Shell>
        <EmptyState title={copy.title} subtitle={copy.subtitle} />
      </Shell>
    );
  }
  if (phase.kind === "notice") {
    return (
      <Shell>
        <p role="alert" className="text-sm" style={{ color: "var(--color-warning)" }}>
          {phase.message}
        </p>
        <Button variant="secondary" onClick={refresh}>
          Try again
        </Button>
        <GameCard />
      </Shell>
    );
  }

  const { data } = phase;
  const forecast = data.forecast!;
  const tone = TONE_COLOR[simOddsTone(forecast.odds.playoffs)];
  const noteLines = simNoteMessages(data.notes);
  const tiles: Array<[string, string, string?]> = [
    ["Playoff odds", simFormatPercent(forecast.odds.playoffs), `${forecast.odds.playoff_spots} teams make it`],
    ["Championship odds", simFormatPercent(forecast.odds.title), `Reach the final: ${simFormatPercent(forecast.odds.finals)}`],
    ["Projected record", forecast.record.projected, `Likely range: ${simWinsRange(forecast.record)}`],
    ["Projected finish", simOrdinal(forecast.finish.median), `Likely range: ${simFinishRange(forecast.finish)} of ${forecast.finish.teams}`],
  ];
  const peak = Math.max(0.01, ...forecast.finish.distribution.map((b) => b.probability));

  return (
    <Shell>
      <SimBanner scope={simScopeLine(forecast, data.mode, data.as_of)} />

      <AccentCard accent={tone} glow>
        <div className="flex items-center gap-4">
          <div
            aria-label={`Playoff odds ${simFormatPercent(forecast.odds.playoffs)}`}
            className="flex items-center justify-center font-extrabold shrink-0"
            style={{ width: 88, height: 88, borderRadius: "var(--radius-pill)", color: tone, fontSize: "1.5rem", background: `color-mix(in srgb, ${tone} 15%, transparent)`, boxShadow: `inset 0 0 0 2px ${tone}` }}
          >
            {simFormatPercent(forecast.odds.playoffs)}
          </div>
          <div className="flex flex-col gap-1 min-w-0">
            <span className="text-xs uppercase font-bold" style={{ color: "var(--color-text-muted)" }}>
              {leagueName}
            </span>
            <span className="text-lg font-bold break-words">{forecast.team.name}</span>
            <span className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
              Now {simFormatCurrent(forecast.current)}
            </span>
          </div>
        </div>
        <p className="text-sm font-semibold">{simHeadline(forecast)}</p>
      </AccentCard>

      <div className="grid grid-cols-2 gap-2">
        {tiles.map(([label, value, sub]) => (
          <div key={label} className="glass-surface p-3 flex flex-col gap-1">
            <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
              {label}
            </span>
            <span className="text-lg font-bold">{value}</span>
            {sub ? (
              <span className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
                {sub}
              </span>
            ) : null}
          </div>
        ))}
      </div>

      <section className="flex flex-col gap-2" aria-labelledby="sim-finish">
        <SectionHeading id="sim-finish" note="How often you land in each spot across the simulated seasons.">
          Where you finish
        </SectionHeading>
        <ul className="flex flex-col gap-1">
          {forecast.finish.distribution.map((bucket) => {
            const inPlayoffs = bucket.finish <= forecast.odds.playoff_spots;
            return (
              <li key={bucket.finish} className="flex items-center gap-2 text-xs">
                <span style={{ width: 36, color: "var(--color-text-secondary)" }}>{simOrdinal(bucket.finish)}</span>
                <span aria-hidden="true" className="flex-1" style={{ height: 8, borderRadius: 4, background: "var(--color-surface-muted)" }}>
                  <span
                    style={{
                      display: "block",
                      height: 8,
                      borderRadius: 4,
                      width: `${(bucket.probability / peak) * 100}%`,
                      background: inPlayoffs ? "var(--color-success)" : "var(--color-border-strong)",
                    }}
                  />
                </span>
                <span style={{ width: 40, textAlign: "right" }}>{simFormatPercent(bucket.probability)}</span>
              </li>
            );
          })}
        </ul>
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          Green spots make the playoffs.
        </p>
      </section>

      <section className="flex flex-col gap-3" aria-labelledby="sim-swing">
        <SectionHeading id="sim-swing" note={simFactorsIntro(forecast.swing_factors)}>
          What swings your season
        </SectionHeading>
        {forecast.swing_factors.map((factor, index) => {
          const good = factor.playoff_delta >= 0;
          return (
            <AccentCard key={`${factor.kind}-${index}`} accent={good ? "var(--color-success)" : "var(--color-warning)"} compact>
              <div className="flex items-center gap-2 flex-wrap">
                <ToneBadge label={simFactorKindLabel(factor.kind)} color={good ? "var(--color-success)" : "var(--color-warning)"} size="xs" />
                <span className="text-xs font-bold">{simFactorImpact(factor)}</span>
              </div>
              <p className="text-sm font-bold">{factor.title}</p>
              <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
                {factor.detail}
              </p>
            </AccentCard>
          );
        })}
      </section>

      <GameCard />

      <Button variant="ghost" onClick={refresh}>
        Refresh forecast
      </Button>
      {noteLines.length > 0 ? (
        <ul className="text-xs flex flex-col gap-1" style={{ color: "var(--color-text-muted)" }}>
          {noteLines.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      ) : null}
    </Shell>
  );
}

function GameCard() {
  return (
    <AccentCard accent="var(--color-premium)">
      <SectionHeading note={SIM_GAME_CARD.body}>{SIM_GAME_CARD.title}</SectionHeading>
      <ButtonLink href="/gm-game" variant="secondary" fullWidth>
        {SIM_GAME_CARD.action}
      </ButtonLink>
    </AccentCard>
  );
}
