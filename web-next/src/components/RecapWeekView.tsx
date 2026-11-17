"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

import { api } from "@/lib/api";
import type { RecapResponse, RecapStory, RecapTradeAsset } from "@/lib/api";
import { EmptyState } from "@/components/EmptyState";
import { Money } from "@/components/Money";
import { ViewSelect } from "@/components/ui/ViewSelect";
import { PageControl } from "@/components/ui/PageControls";
import { SkeletonModule, SkeletonRegion, SkeletonStatusHeader } from "@/components/Skeleton";
import { TeamAvatar } from "@/components/TeamAvatar";
import { CompactModule } from "@/components/ui/CompactModule";
import { ModuleMore } from "@/components/ui/ModuleMore";
import { PlayerAccordionRow, usePlayerAccordion } from "@/components/ui/PlayerAccordionRow";
import { PresenceSwap } from "@/components/ui/Presence";
import { StatusHeader } from "@/components/ui/StatusHeader";
import { TradeAssetCard, TradeCompactCard, type TradeCardAsset } from "@/components/ui/TradeCompactCard";
import { FILTER_ALL, historyDeepLinkLabel } from "@/lib/leagueRecapsPresentation";
import { buildRecapPage, isMatchupStory, recapFaab, recapMetric, recapScoreline, recapWeekChips, storyInvolves, type RecapSection } from "@/lib/recapPage";
import { formatMoney } from "@/lib/money";

import dynamic from "next/dynamic";

// Perf pass 2026-11: the manager sheet only mounts after a tap on a team, so it is its own chunk instead of first-load JS.
const ManagerProfileSheet = dynamic(() => import("@/components/ManagerProfileSheet").then((m) => m.ManagerProfileSheet), {
  loading: () => null,
});

/**
 * The weekly recap (League > Recaps > "Recaps"), built from the shared templates (docs/ui-patterns.md, "Weekly recap
 * page"): ONE week strip (the shared PillRow, snap + centred active week), a StatusHeader with the week's result, then a
 * CompactModule per kind of story (scoring, matchups, waivers, trades, activity) that expands in place into team rows
 * with crests, player rows with avatars and the shared trade card. Gold marks only the week's scoring leader. Every
 * value comes from `GET .../recap` (and the league's team profiles for the crests); nothing is derived beyond that.
 * App twin: mobile/src/screens/RecapScreen.tsx; model: lib/recapPage.ts.
 */

interface TeamIdentity {
  name: string;
  ownerName: string | null;
  avatarUrl: string | null;
}

type OpenTeam = (rosterId: string, fallbackName: string) => void;

const MUTED = { color: "var(--color-text-muted)" } as const;
const GOLD = "var(--color-prestige-elite)";

function YouChip() {
  return (
    <span
      className="inline-flex shrink-0 items-center px-1.5 text-[0.6875rem] font-extrabold uppercase"
      style={{ height: 18, borderRadius: "var(--radius-pill)", color: "var(--color-accent)", background: "color-mix(in srgb, var(--color-accent) 14%, transparent)", letterSpacing: "var(--letter-spacing-badge)" }}
    >
      You
    </span>
  );
}

/** A team: crest, name (never cut off), an optional "You" marker and one trailing figure. Taps open the manager profile. */
function TeamRow({
  name,
  rosterId,
  identity,
  mine,
  trailing,
  sub,
  muted = false,
  ring,
  openTeam,
}: {
  name: string;
  rosterId: string;
  identity: TeamIdentity | undefined;
  mine: boolean;
  trailing?: ReactNode;
  sub?: string;
  muted?: boolean;
  ring?: string;
  openTeam: OpenTeam;
}) {
  const body = (
    <>
      <TeamAvatar avatarUrl={identity?.avatarUrl} name={identity?.name || name} size={32} ringColor={ring} />
      <span className="flex min-w-0 flex-1 flex-col">
        <span className="flex min-w-0 flex-wrap items-center gap-x-1.5">
          <span className="min-w-0 break-words text-sm font-bold" style={{ color: muted ? "var(--color-text-secondary)" : "var(--color-text-primary)" }}>
            {name}
          </span>
          {mine ? <YouChip /> : null}
        </span>
        {sub ? (
          <span className="text-xs" style={MUTED}>
            {sub}
          </span>
        ) : null}
      </span>
      {trailing ? <span className="flex shrink-0 flex-col items-end text-base font-extrabold tabular-nums">{trailing}</span> : null}
    </>
  );
  if (!rosterId) {
    return (
      <div className="flex min-w-0 items-center gap-2.5" style={{ minHeight: "var(--touch-target-min)" }}>
        {body}
      </div>
    );
  }
  return (
    <button
      type="button"
      onClick={() => openTeam(rosterId, name)}
      aria-label={`${name}, open manager profile`}
      className="flex w-full min-w-0 items-center gap-2.5 text-left"
      style={{ minHeight: "var(--touch-target-min)", background: "none", border: 0, padding: 0, color: "inherit" }}
    >
      {body}
    </button>
  );
}

function Chip({ children, tone }: { children: ReactNode; tone?: "success" | "accent" }) {
  const color = tone === "success" ? "var(--color-success)" : tone === "accent" ? "var(--color-accent)" : "var(--color-text-secondary)";
  return (
    <span
      className="inline-flex items-center px-2 text-xs font-bold"
      style={{ minHeight: 24, borderRadius: "var(--radius-pill)", color, background: `color-mix(in srgb, ${color} 12%, transparent)`, boxShadow: `inset 0 0 0 1px color-mix(in srgb, ${color} 28%, transparent)` }}
    >
      {children}
    </span>
  );
}

function StoryFrame({ story, children, onOpenHistory }: { story: RecapStory; children: ReactNode; onOpenHistory: (filter: string) => void }) {
  const link = historyDeepLinkLabel(story);
  return (
    <div className="flex min-w-0 flex-col gap-1.5" data-testid="recap-story" data-story-type={story.story_type}>
      <span className="text-xs font-bold" style={{ color: "var(--color-text-secondary)" }}>
        {story.title}
      </span>
      {children}
      {story.summary ? (
        <p className="m-0 text-sm" style={{ color: "var(--color-text-secondary)" }}>
          {story.summary}
        </p>
      ) : null}
      {story.editorial_label ? (
        <span className="self-start">
          <Chip>{story.editorial_label}</Chip>
        </span>
      ) : null}
      {link ? <ModuleMore onClick={() => onOpenHistory(story.history_filter || FILTER_ALL)}>{link}</ModuleMore> : null}
    </div>
  );
}

function tradeAsset(asset: RecapTradeAsset, key: string): TradeCardAsset {
  if (asset.kind === "pick") return { key, pickLabel: asset.label || asset.name };
  return { key, player: { id: asset.player_id || null, name: asset.name, position: asset.position ?? null, team: asset.team ?? null } };
}

function tradeSides(story: RecapStory): { team_name: string; roster_id: string; assets: RecapTradeAsset[] }[] {
  if (story.sides && story.sides.length > 0) return story.sides.map((s) => ({ team_name: s.team_name, roster_id: s.roster_id, assets: s.assets ?? [] }));
  return [
    { team_name: story.primary_team, roster_id: story.primary_roster_id, assets: story.left_assets ?? [] },
    { team_name: story.secondary_team, roster_id: story.secondary_roster_id, assets: story.right_assets ?? [] },
  ].filter((s) => s.team_name);
}

function TradeStory({ story, myRosterId, onOpenHistory }: { story: RecapStory; myRosterId: string; onOpenHistory: (filter: string) => void }) {
  const sides = tradeSides(story);
  const link = historyDeepLinkLabel(story);
  const details = (
    <>
      {story.value_lenses?.map((lens) => (
        <p key={lens.lens} className="m-0 text-xs" style={MUTED}>
          {lens.label}: {lens.note}
        </p>
      ))}
      {link ? <ModuleMore onClick={() => onOpenHistory(story.history_filter || FILTER_ALL)}>{link}</ModuleMore> : null}
    </>
  );
  const hasAssets = sides.some((s) => s.assets.length > 0);
  const mineIn = storyInvolves(story, myRosterId);
  if (hasAssets && sides.length === 2) {
    return (
      <TradeCompactCard
        title={
          <span className="break-words">
            {story.title}
            {mineIn ? " · you" : ""}
          </span>
        }
        give={sides[0].assets.map((a, i) => tradeAsset(a, `a${i}`))}
        get={sides[1].assets.map((a, i) => tradeAsset(a, `b${i}`))}
        giveLabel={`${sides[0].team_name} got`}
        getLabel={`${sides[1].team_name} got`}
        meta={[story.editorial_label ?? ""].filter(Boolean)}
        meter={null}
        testId="recap-trade-card"
      >
        {story.summary ? (
          <p className="m-0 text-sm" style={{ color: "var(--color-text-secondary)" }}>
            {story.summary}
          </p>
        ) : null}
        {details}
      </TradeCompactCard>
    );
  }
  return (
    <section className="glass-surface flex min-w-0 flex-col gap-2 p-3" style={{ borderRadius: "var(--radius-panel)" }} data-testid="recap-trade-card">
      <div className="min-w-0 break-words text-sm font-extrabold">{story.title}</div>
      {sides.map((side, i) => (
        <div key={`${side.roster_id}-${i}`} className="flex min-w-0 flex-col gap-1">
          <span className="break-words text-[0.6875rem] font-extrabold uppercase" style={{ ...MUTED, letterSpacing: "var(--letter-spacing-badge)" }}>
            {side.team_name} got
          </span>
          {side.assets.map((a, j) => (
            <TradeAssetCard key={j} asset={tradeAsset(a, `s${i}-${j}`)} mode="desk" />
          ))}
        </div>
      ))}
      {story.summary ? (
        <p className="m-0 text-sm" style={{ color: "var(--color-text-secondary)" }}>
          {story.summary}
        </p>
      ) : null}
      {details}
    </section>
  );
}

function WaiverStory({
  story,
  idKey,
  identity,
  myRosterId,
  openTeam,
  acc,
  onOpenHistory,
}: {
  story: RecapStory;
  idKey: string;
  identity: TeamIdentity | undefined;
  myRosterId: string;
  openTeam: OpenTeam;
  acc: ReturnType<typeof usePlayerAccordion>;
  onOpenHistory: (filter: string) => void;
}) {
  const asset = story.player_assets?.find((a) => a.player_id);
  const faab = recapFaab(story);
  const mine = story.primary_roster_id === myRosterId && Boolean(myRosterId);
  if (!asset) {
    return (
      <StoryFrame story={story} onOpenHistory={onOpenHistory}>
        <TeamRow name={story.primary_team} rosterId={story.primary_roster_id} identity={identity} mine={mine} openTeam={openTeam} trailing={faab != null ? <Money all>{formatMoney(faab)}</Money> : undefined} sub={story.players.join(", ")} />
      </StoryFrame>
    );
  }
  return (
    <div className="flex min-w-0 flex-col" data-testid="recap-story" data-story-type={story.story_type}>
      <span className="text-xs font-bold" style={{ color: "var(--color-text-secondary)" }}>
        {story.title}
      </span>
      <PlayerAccordionRow
        player={{ id: asset.player_id, name: asset.name, position: asset.position ?? null, team: asset.team ?? null }}
        mode="desk"
        metaText={[asset.team, "Added"].filter(Boolean).join(" · ")}
        trailingFact={faab != null ? { key: "faab", label: "FAAB", value: formatMoney(faab), tone: "success" } : null}
        open={acc.isOpen(idKey)}
        onToggle={() => acc.toggle(idKey)}
        testId="recap-waiver-row"
      >
        <TeamRow name={story.primary_team} rosterId={story.primary_roster_id} identity={identity} mine={mine} openTeam={openTeam} sub="Claimed by" />
        {story.summary ? (
          <p className="m-0 text-sm" style={{ color: "var(--color-text-secondary)" }}>
            {story.summary}
          </p>
        ) : null}
        <ModuleMore onClick={() => onOpenHistory(story.history_filter || FILTER_ALL)}>{historyDeepLinkLabel(story) || "View waiver history"}</ModuleMore>
      </PlayerAccordionRow>
    </div>
  );
}

function StoryBody({
  story,
  idKey,
  identities,
  myRosterId,
  openTeam,
  acc,
  onOpenHistory,
}: {
  story: RecapStory;
  idKey: string;
  identities: Record<string, TeamIdentity>;
  myRosterId: string;
  openTeam: OpenTeam;
  acc: ReturnType<typeof usePlayerAccordion>;
  onOpenHistory: (filter: string) => void;
}) {
  const mine = (rosterId: string) => Boolean(myRosterId) && rosterId === myRosterId;
  if (story.story_type === "trade") return <TradeStory story={story} myRosterId={myRosterId} onOpenHistory={onOpenHistory} />;
  if (story.story_type === "waiver" || story.story_type === "waiver_low") {
    return <WaiverStory story={story} idKey={idKey} identity={identities[story.primary_roster_id]} myRosterId={myRosterId} openTeam={openTeam} acc={acc} onOpenHistory={onOpenHistory} />;
  }
  if (isMatchupStory(story)) {
    const score = recapScoreline(story);
    return (
      <StoryFrame story={story} onOpenHistory={onOpenHistory}>
        <div className="flex min-w-0 flex-col">
          <TeamRow name={story.primary_team} rosterId={story.primary_roster_id} identity={identities[story.primary_roster_id]} mine={mine(story.primary_roster_id)} openTeam={openTeam} trailing={score ? score.winner : undefined} sub="Won" />
          <TeamRow name={story.secondary_team} rosterId={story.secondary_roster_id} identity={identities[story.secondary_roster_id]} mine={mine(story.secondary_roster_id)} openTeam={openTeam} trailing={score ? score.loser : undefined} sub="Lost" muted />
        </div>
        {recapMetric(story) ? (
          <span className="self-start">
            <Chip tone="accent">
              {story.metric_label || "Margin"} {recapMetric(story)}
            </Chip>
          </span>
        ) : null}
      </StoryFrame>
    );
  }
  const metric = recapMetric(story);
  const isPoints = story.story_type.startsWith("performance");
  return (
    <StoryFrame story={story} onOpenHistory={onOpenHistory}>
      <TeamRow
        name={story.primary_team}
        rosterId={story.primary_roster_id}
        identity={identities[story.primary_roster_id]}
        mine={mine(story.primary_roster_id)}
        openTeam={openTeam}
        sub={isPoints ? undefined : story.metric_label || undefined}
        trailing={
          metric ? (
            <>
              <span>
                <Money>{metric}</Money>
              </span>
              {isPoints ? (
                <span className="text-[0.6875rem] font-extrabold uppercase" style={{ ...MUTED, letterSpacing: "var(--letter-spacing-badge)" }}>
                  Points
                </span>
              ) : null}
            </>
          ) : undefined
        }
      />
      {story.players.length > 0 && story.story_type !== "trade" ? (
        <div className="flex flex-wrap gap-1.5">
          {story.players.map((name) => (
            <Chip key={name}>{name}</Chip>
          ))}
        </div>
      ) : null}
    </StoryFrame>
  );
}

function RecapSkeleton() {
  return (
    <SkeletonRegion label="Weekly recap" className="flex flex-col gap-2">
      <SkeletonStatusHeader rows={0} />
      <SkeletonModule lines={2} />
      <SkeletonModule lines={2} />
      <SkeletonModule lines={2} />
    </SkeletonRegion>
  );
}

function SectionModule({
  section,
  index,
  identities,
  myRosterId,
  openTeam,
  onOpenHistory,
}: {
  section: RecapSection;
  index: number;
  identities: Record<string, TeamIdentity>;
  myRosterId: string;
  openTeam: OpenTeam;
  onOpenHistory: (filter: string) => void;
}) {
  const acc = usePlayerAccordion();
  return (
    <CompactModule id={`recap.${section.key}`} title={section.title} parts={section.parts} defaultOpen={index === 0} testId={`recap-section-${section.key}`}>
      {section.stories.map((story, i) => (
        <StoryBody key={`${story.story_type}-${i}`} story={story as RecapStory} idKey={`${story.story_type}-${i}`} identities={identities} myRosterId={myRosterId} openTeam={openTeam} acc={acc} onOpenHistory={onOpenHistory} />
      ))}
    </CompactModule>
  );
}

export function RecapWeekView({ leagueId, leagueName, initial, onOpenHistory }: { leagueId: string; leagueName: string; initial: RecapResponse; onOpenHistory: (filter: string) => void }) {
  const [data, setData] = useState<RecapResponse>(initial);
  const [selectedWeek, setSelectedWeek] = useState<number>(initial.recap?.week ?? initial.max_completed_week);
  const [loading, setLoading] = useState(false);
  const [identities, setIdentities] = useState<Record<string, TeamIdentity>>({});
  const [profile, setProfile] = useState<{ rosterId: string; teamName: string } | null>(null);
  const [myRosterId, setMyRosterId] = useState(initial.my_roster_id ?? "");
  const requestRef = useRef(0);

  // Crests: the league's team profiles (best effort; a miss just shows the initials ring).
  useEffect(() => {
    let cancelled = false;
    api
      .getLeagueTeamProfiles(leagueId)
      .then((res) => {
        if (cancelled || !res?.profiles) return;
        const next: Record<string, TeamIdentity> = {};
        for (const [rosterId, p] of Object.entries(res.profiles)) next[String(rosterId)] = { name: p.team_name, ownerName: p.owner_name || null, avatarUrl: p.avatar_url || null };
        setIdentities(next);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [leagueId]);

  const loadWeek = (week: number) => {
    if (week === selectedWeek && !loading) return;
    const request = ++requestRef.current;
    setSelectedWeek(week);
    setLoading(true);
    api
      .getLeagueRecap(leagueId, week, true)
      .then((response) => {
        if (request !== requestRef.current) return;
        setData(response);
        if (response.my_roster_id) setMyRosterId(response.my_roster_id);
      })
      .catch(() => undefined)
      .finally(() => {
        if (request === requestRef.current) setLoading(false);
      });
  };

  if (data.reason === "no_completed_week" || !data.recap) {
    return (
      <EmptyState
        title="No recap yet"
        subtitle="No completed week is ready for a recap yet. Open History for the recorded transaction timeline."
        actionLabel="Open History"
        onAction={() => onOpenHistory("")}
      />
    );
  }

  const recap = data.recap;
  const page = buildRecapPage(recap, myRosterId);
  const openTeam: OpenTeam = (rosterId, fallbackName) => setProfile({ rosterId, teamName: identities[rosterId]?.name || fallbackName });
  const chips = recapWeekChips(data.max_completed_week);

  const header = (
    <StatusHeader
      model={{ kicker: page.hero.kicker, headline: page.hero.headline, context: page.hero.context, ring: page.hero.ring, stats: page.hero.stats, attention: [], primary: null }}
      testId="recap-status-header"
    >
      {page.hero.leader ? (
        <div className="glass-surface flex min-w-0 items-center gap-2.5 px-3" style={{ borderRadius: "var(--radius-card, 12px)", minHeight: "var(--touch-target-min)" }} data-testid="recap-leader">
          <span className="flex min-w-0 flex-1">
            <TeamRow
              name={page.hero.leader.team}
              rosterId={page.hero.leader.rosterId}
              identity={identities[page.hero.leader.rosterId]}
              mine={Boolean(myRosterId) && page.hero.leader.rosterId === myRosterId}
              ring={GOLD}
              sub="Scoring leader"
              trailing={page.hero.leader.points}
              openTeam={openTeam}
            />
          </span>
        </div>
      ) : null}
      {recap.incomplete || page.sections.length === 0 ? (
        <p className="m-0 text-sm" style={MUTED}>
          {recap.empty_reason || "Not enough historical data for a recap this week."}
        </p>
      ) : (
        page.sections.map((section, index) => (
          <SectionModule key={section.key} section={section} index={index} identities={identities} myRosterId={myRosterId} openTeam={openTeam} onOpenHistory={onOpenHistory} />
        ))
      )}
    </StatusHeader>
  );

  return (
    <div className="flex flex-col gap-3" data-testid="recap-week-view">
      {chips.length > 1 ? (
        <PageControl>
          <ViewSelect label="Recap week" className="min-w-0 flex-1" value={String(selectedWeek)} options={chips} onChange={(value) => loadWeek(Number(value))} />
        </PageControl>
      ) : null}
      {loading ? <RecapSkeleton /> : <PresenceSwap swapKey={`week-${recap.week}`}>{header}</PresenceSwap>}
      {profile ? <ManagerProfileSheet leagueId={leagueId} leagueName={leagueName} rosterId={profile.rosterId} teamName={profile.teamName} ownerName={identities[profile.rosterId]?.ownerName ?? null} avatarUrl={identities[profile.rosterId]?.avatarUrl ?? null} onClose={() => setProfile(null)} /> : null}
    </div>
  );
}
