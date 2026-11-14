"use client";

import { useEffect, useState } from "react";

import { AccentCard } from "@/components/AccentCard";
import { ButtonLink } from "@/components/Button";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { failureMessage } from "@/components/MultiTeamTradeContent";
import { PitchShareButton } from "@/components/MultiTeamPitchButton";
import { PremiumUpsellCard } from "@/components/PremiumUpsellCard";
import { SkeletonCard } from "@/components/Skeleton";
import { ToneBadge } from "@/components/ToneBadge";
import { CompactModule } from "@/components/ui/CompactModule";
import { compactCount } from "@/lib/compactModule";
import { trackUse } from "@/lib/analytics";
import { api } from "@/lib/api";
import {
  ideaAnalyzerQuery,
  ideaAsResponse,
  ideaTeamLines,
  ideasSection,
  lockedTeaserTitle,
  type MultiTeamIdea,
  type MultiTeamIdeasResponse,
} from "@/lib/multiTeamIdeas";
import { toneSemantic, type SemanticTone } from "@/lib/multiTeamTrade";

const TONE_VAR: Record<SemanticTone, string> = {
  success: "var(--color-success)",
  neutral: "var(--color-text-secondary)",
  warning: "var(--color-warning)",
  danger: "var(--color-danger)",
};

/**
 * "3-team ideas" in Trade Hub: cyclic three-way deals where every team's own
 * verdict is Fair or better (GET .../trade-ideas/multi, modules/
 * multi_team_trade_finder.py). Pro sees the ideas; Free sees a locked teaser
 * with the count. Each idea opens the multi-team Analyzer prefilled (it
 * regrades the deal) and shares the same pitch card the Analyzer does.
 */
export function MultiTeamIdeasSection({ leagueId, leagueName, lens }: { leagueId: string; leagueName: string; lens: string }) {
  const [attempt, setAttempt] = useState(0);
  const [response, setResponse] = useState<MultiTeamIdeasResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    // A new attempt or lens starts a fresh load (the busy retry itself lives in the API client).
    queueMicrotask(() => {
      if (cancelled) return;
      setResponse(null);
      setError(null);
    });
    api
      .getMultiTeamTradeIdeas(leagueId, lens)
      .then((result) => {
        if (!cancelled) setResponse(result);
      })
      .catch((err) => {
        if (!cancelled) setError(failureMessage(err));
      });
    return () => {
      cancelled = true;
    };
  }, [leagueId, lens, attempt]);

  const section = response ? ideasSection(response) : null;
  const parts = error
    ? [{ key: "e", text: "Couldn't load 3-team ideas", tone: "danger" as const }]
    : !section
      ? [{ key: "l", text: "Looking for 3-team deals" }]
      : section.kind === "ideas"
        ? [{ key: "n", text: compactCount(section.ideas.length, "3-team deal"), strong: true }, { key: "f", text: "fair for every team" }]
        : section.kind === "locked"
          ? [{ key: "n", text: lockedTeaserTitle(section.count), strong: true }, { key: "p", text: "Pro", tone: "action" as const }]
          : [{ key: "m", text: section.kind === "closed" ? "Trading is closed" : "No 3-team deals right now" }];
  return (
    <CompactModule id="trades.multi" title="3-team ideas" testId="multi-team-ideas" tone="action" parts={parts}>
      <p className="text-sm m-0" style={{ color: "var(--color-text-secondary)" }}>
        Three-way deals where your surplus players and picks fill one team&apos;s need, theirs fills another&apos;s, and every team still comes out fair.
      </p>
      <IdeasBody
        leagueId={leagueId}
        leagueName={leagueName}
        response={response}
        error={error}
        onRetry={() => setAttempt((n) => n + 1)}
      />
    </CompactModule>
  );
}

function IdeasBody({
  leagueId,
  leagueName,
  response,
  error,
  onRetry,
}: {
  leagueId: string;
  leagueName: string;
  response: MultiTeamIdeasResponse | null;
  error: string | null;
  onRetry: () => void;
}) {
  if (error) return <ErrorState bare message={error} onRetry={onRetry} />;
  if (!response) return <IdeasSkeleton />;
  const section = ideasSection(response);
  if (section.kind === "locked") {
    return (
      <PremiumUpsellCard
        bare
        kicker="3-team ideas"
        leagueName={leagueName}
        upsell={response.upsell ? { title: response.upsell.title ?? "", body: response.upsell.body ?? "" } : null}
        fallbackTitle={lockedTeaserTitle(section.count)}
        fallbackBody="Pro finds three-way deals where every team still comes out fair."
        example={lockedTeaserTitle(section.count)}
      />
    );
  }
  if (section.kind === "empty" || section.kind === "closed") {
    return <EmptyState title={section.kind === "closed" ? "Trading is closed" : "No 3-team deals right now"} subtitle={section.message} />;
  }
  return (
    <div className="flex flex-col gap-4" data-testid="multi-team-idea-list">
      {section.ideas.map((idea) => (
        <IdeaCard key={idea.id} idea={idea} leagueId={leagueId} leagueName={leagueName} />
      ))}
    </div>
  );
}

function IdeasSkeleton() {
  return (
    <div className="flex flex-col gap-3" aria-busy="true" data-testid="multi-team-ideas-skeleton">
      <span className="sr-only" role="status">
        Looking for 3-team deals
      </span>
      <SkeletonCard lines={4} />
      <SkeletonCard lines={4} />
    </div>
  );
}

function IdeaCard({ idea, leagueId, leagueName }: { idea: MultiTeamIdea; leagueId: string; leagueName: string }) {
  const lines = ideaTeamLines(idea);
  const you = idea.user;
  const accent = TONE_VAR[toneSemantic(you.outcome === "wins" ? "accept" : "fair")];
  return (
    <AccentCard accent={accent} as="article" data-testid="multi-team-idea">
      <div className="flex flex-wrap items-center gap-2">
        <ToneBadge label="3-team" color="var(--color-information)" />
        {idea.variant ? <ToneBadge label="One added piece" color="var(--color-text-secondary)" title={idea.variant.note} /> : null}
      </div>
      <p className="text-base font-black m-0">{idea.headline}</p>
      <p className="text-sm m-0" style={{ color: "var(--color-text-secondary)" }} data-testid="idea-you-delta">
        For you: value {lines[0]?.valueChange ?? "0"}
        {Math.abs(you.lineup_delta?.per_week ?? 0) >= 0.5
          ? `, lineup ${you.lineup_delta.per_week > 0 ? "+" : ""}${you.lineup_delta.per_week.toFixed(1)} pts a week`
          : ""}
        .
      </p>
      <ul className="flex flex-col gap-2 m-0 p-0 list-none">
        {lines.map((line) => (
          <li key={line.rosterId} className="flex flex-col gap-1 min-w-0" data-testid="idea-team-line">
            <div className="flex flex-wrap items-center gap-2">
              <strong className="text-sm min-w-0 break-words">{line.name}</strong>
              <ToneBadge label={line.verdict} color={TONE_VAR[toneSemantic(line.tone)]} />
              <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                value {line.valueChange}
              </span>
            </div>
            <p className="text-sm m-0 break-words" style={{ color: "var(--color-text-secondary)" }}>
              Gets {line.gets}. Sends {line.sends}.
            </p>
            {line.why ? (
              <p className="text-xs m-0 break-words" style={{ color: "var(--color-text-muted)" }}>
                {line.why}
              </p>
            ) : null}
          </li>
        ))}
      </ul>
      {idea.variant ? (
        <p className="text-xs m-0" style={{ color: "var(--color-text-muted)" }}>
          {idea.variant.note}
        </p>
      ) : null}
      <div className="flex flex-wrap items-center gap-2">
        <ButtonLink
          href={`/trade-analyzer/${encodeURIComponent(leagueId)}?${ideaAnalyzerQuery(leagueName, idea)}`}
          size="sm"
          onClick={() => trackUse("trade_hub", "multi_idea_opened", { leagueId })}
        >
          Open in Analyzer
        </ButtonLink>
        <PitchShareButton response={ideaAsResponse(idea)} leagueId={leagueId} leagueName={leagueName} itemKind="multi_team_idea" label="Share the pitch" />
      </div>
    </AccentCard>
  );
}
