"use client";

import { HelpLink } from "@/components/HelpLink";
import { useState, type ReactNode } from "react";

import { api, type SaveLeagueResponse, type SleeperLeagueSummary } from "@/lib/api";
import { LEAGUE_CAP_UPSELL, isSaveFailure, saveFailureMessage } from "@/lib/leagueSave";
import { PremiumUpsellCard } from "@/components/PremiumUpsellCard";
import { useAuth } from "@/context/AuthContext";
import { trackFeatureUse } from "@/lib/analytics";
import { clearPendingReferralCode, getPendingReferralCode } from "@/lib/attribution";
import { SampleLeagueButton } from "@/components/SampleLeagueBanner";
import { describeSleeperConnectError, isConnectivityFailure, type SleeperConnectError } from "@/lib/sleeperConnectErrors";
import { EspnImportForm } from "@/components/EspnImportForm";
import { LeagueWarmupProgress } from "@/components/LeagueWarmupProgress";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { SkeletonRows } from "@/components/Skeleton";
import { TeamAvatar } from "@/components/TeamAvatar";
import {
  CONNECT_FIELD_LABEL,
  CONNECT_MORE_LABEL,
  CONNECT_PLACEHOLDER,
  CONNECT_PRIMARY_LABEL,
  CONNECT_TRUST_LINE,
  CONNECT_WHAT_IS_SLEEPER,
  connectCtaLabel,
  connectWays,
  defaultLeagueSelection,
  groupLeaguesBySeason,
  leagueMeta,
  planSaves,
  summarizeSaves,
  toggleLeague,
  type SaveOutcome,
} from "@/lib/connectFlow";

/**
 * Ports app.py's guest Sleeper-username import (load_leagues_for_username /
 * the launch form, app.py:13617-13712, 6268-6350): a single username input,
 * "Load my leagues" CTA, auto-continue on exactly one eligible league, a
 * picker when there's more than one. Requires a Supabase session first
 * (anonymous "guest" or signed-in) — see AuthContext's signInAsGuest and
 * the PR description for why this mirrors mobile's reference
 * implementation rather than Streamlit's sessionless guest model.
 *
 * Audit finding, 2026-10-20: this is web-next's only "connect a Sleeper
 * league" flow (reached both from "/" onboarding and from /connect-league),
 * and it had zero analytics wiring -- the entire League Import funnel step
 * (modules.launch_analytics.FUNNEL_STEPS' "League Import": "league_import_
 * completed") and the sleeper_connected relaunch-taxonomy event had never
 * fired once from web-next. The four events wired below
 * (sleeper_connected, league_import_started, league_import_completed,
 * league_import_failed) are all pre-existing TRACKED_EVENTS entries;
 * placement/once_key choices mirror app.py's own emission sites for the
 * same user actions (load_leagues_for_username / set_selected_league)
 * exactly, so Founder Analytics' funnel keeps the same semantics it
 * already has for the legacy surface.
 */
type LeaguePlatform = "sleeper" | "espn" | "fleaflicker" | "mfl";

/**
 * The Connect League flow, one field first (UI pass 3, sheet 1 topic 2 V1; copy and rules in lib/connectFlow.ts):
 * a Sleeper username and one "Connect" button, an instant league list with avatars and checkboxes, then optional
 * steps. ESPN / Fleaflicker / MFL, an account and the sample league are compact rows under "More ways to connect",
 * so every previous capability is still one tap away. Mobile twin: the Add league sheet in screens/HomeScreen.tsx.
 */
export function SleeperImportForm({
  onLeagueChosen,
  sampleCtaBelow = false,
  onStartSession,
  accountSlot,
}: {
  onLeagueChosen: (leagueId: string, leagueName: string) => void;
  /** The caller already renders its own "Try a sample league" button under this
   * form; skip the one the error state would add so the user never sees two. */
  sampleCtaBelow?: boolean;
  /** Fires right before a disposable guest session is created by Connect (the landing keeps the form mounted). */
  onStartSession?: () => void;
  /** Rendered under "More ways to connect" > account (sign in / create an account). Omitted: no account row. */
  accountSlot?: ReactNode;
}) {
  const [platform, setPlatform] = useState<LeaguePlatform>("sleeper");
  const [moreOpen, setMoreOpen] = useState(false);
  const [accountOpen, setAccountOpen] = useState(false);
  const ways = connectWays({ hasAccount: !accountSlot });
  const onWay = (key: string) => {
    if (key === "espn" || key === "fleaflicker" || key === "mfl") setPlatform(key);
    if (key === "account") setAccountOpen((open) => !open);
  };
  return (
    <div className="flex flex-col gap-3">
      {platform !== "sleeper" ? (
        <div className="flex flex-col gap-2">
          <button type="button" onClick={() => setPlatform("sleeper")} className="tap-link self-start text-sm font-bold" style={{ color: "var(--color-accent)", minHeight: "var(--touch-target-min)" }}>
            ← Use my Sleeper username
          </button>
          {/* key: switching platform resets the form (league id, preview, team pick). */}
          <EspnImportForm key={platform} platform={platform} onLeagueChosen={onLeagueChosen} />
        </div>
      ) : (
        <SleeperUsernameImport onLeagueChosen={onLeagueChosen} sampleCtaBelow={sampleCtaBelow} onStartSession={onStartSession} />
      )}
      <div className="flex flex-col gap-2" data-testid="more-ways">
        <button
          type="button"
          aria-expanded={moreOpen}
          onClick={() => setMoreOpen(!moreOpen)}
          className="tap-link flex items-center justify-between text-sm font-bold"
          style={{ minHeight: "var(--touch-target-min)", color: "var(--color-text-secondary)" }}
        >
          <span>{CONNECT_MORE_LABEL}</span>
          <span aria-hidden="true">{moreOpen ? "−" : "+"}</span>
        </button>
        {moreOpen ? (
          <ul className="m-0 flex list-none flex-col gap-2 p-0 motion-in" data-motion="in">
            {ways.map((way) => (
              <li key={way.key}>
                {way.key === "sample" ? (
                  <SampleLeagueButton surface="connect_step" variant="secondary" />
                ) : (
                  <button
                    type="button"
                    onClick={() => onWay(way.key)}
                    aria-expanded={way.key === "account" ? accountOpen : undefined}
                    className="glass-surface flex w-full flex-col items-start gap-0.5 px-3 py-2 text-left"
                    style={{ minHeight: "var(--touch-target-min)", color: "var(--color-text-primary)" }}
                  >
                    <span className="text-sm font-bold">{way.label}</span>
                    <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                      {way.blurb}
                    </span>
                  </button>
                )}
                {way.key === "account" && accountOpen ? <div className="mt-2">{accountSlot}</div> : null}
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </div>
  );
}

function SleeperUsernameImport({
  onLeagueChosen,
  sampleCtaBelow,
  onStartSession,
}: {
  onLeagueChosen: (leagueId: string, leagueName: string) => void;
  sampleCtaBelow: boolean;
  onStartSession?: () => void;
}) {
  const { signInAsGuest, session } = useAuth();
  const [username, setUsername] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "saving" | "error">("idle");
  const [message, setMessage] = useState<string | null>(null);
  // Structured error from lib/sleeperConnectErrors (the single copy source):
  // user_not_found / no_leagues / network each get their own guidance, plus
  // the sample-league and "no Sleeper account yet" paths (onboarding audit,
  // 2026-10-18; connect-failure analytics, 2026-10).
  const [connectError, setConnectError] = useState<SleeperConnectError | null>(null);
  const [leagues, setLeagues] = useState<SleeperLeagueSummary[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [whatIsOpen, setWhatIsOpen] = useState(false);
  // Set once a save reports the server is warming the league's first-load
  // data; shows real progress until it is ready, then continues.
  const [warming, setWarming] = useState<{ leagueId: string; name: string } | null>(null);

  // Set when the server refuses a save because the plan's league cap is hit. `open` is the league that DID save (if any).
  const [atCap, setAtCap] = useState<{ open: { leagueId: string; leagueName: string } | null } | null>(null);

  // Returns false (and never opens the league) unless the server saved it.
  const finishSave = (saved: SaveLeagueResponse): boolean => {
    if (isSaveFailure(saved)) {
      if (saved?.reason === "at_cap") {
        setStatus("idle");
        setAtCap({ open: null });
      } else {
        setStatus("error");
        setMessage(saveFailureMessage(saved?.reason));
      }
      trackFeatureUse("league_import_failed", { dedupe: false, props: { reason: saved?.reason || "unavailable" } });
      return false;
    }
    return true;
  };

  const continueAfterSave = (saved: SaveLeagueResponse, leagueId: string, name: string) => {
    if (saved?.warming) {
      setWarming({ leagueId, name });
      return;
    }
    onLeagueChosen(leagueId, name);
  };

  const handleSubmit = async (event?: React.FormEvent) => {
    event?.preventDefault();
    const clean = username.trim();
    if (!clean) return;

    setStatus("loading");
    setMessage(null);
    setConnectError(null);
    setLeagues([]);
    // Mirrors app.py's load_leagues_for_username, which fires this on every
    // lookup attempt (once per session) regardless of outcome -- this is
    // the "attempted a Sleeper connect" signal, not "succeeded".
    trackFeatureUse("league_import_started");

    try {
      if (!session) {
        onStartSession?.();
        const { error } = await signInAsGuest();
        if (error) {
          setStatus("error");
          setMessage(error);
          return;
        }
      }

      // Redeem a captured /?ref=CODE invite on the first username that
      // resolves (the server only credits it once and ignores bad codes).
      const pendingRef = getPendingReferralCode();
      const result = pendingRef ? await api.lookupSleeperLeagues(clean, pendingRef) : await api.lookupSleeperLeagues(clean);
      if (pendingRef && result.ok) clearPendingReferralCode();
      if (result.ok) {
        // Mirrors app.py: the username itself resolved on Sleeper's side
        // (even a zero-leagues account counts here, same as lookup.status
        // "ok" or "no_leagues" there) -- this is identity resolution, not
        // league selection, so it fires before the leagues.length check.
        trackFeatureUse("sleeper_connected");
      }
      if (!result.ok || result.leagues.length === 0) {
        setStatus("error");
        setConnectError(
          describeSleeperConnectError({
            status: result.ok ? "no_leagues" : result.status,
            username: clean,
            serverMessage: result.message,
          }),
        );
        if (!result.ok) {
          trackFeatureUse("league_import_failed", { dedupe: false, props: { reason: result.status || "unavailable" } });
        }
        return;
      }

      // Link the username so the Dashboard's roster-resolution (GET
      // .../dashboard -> _resolve_my_roster) can find "my roster" by
      // owner_id once a league is opened (see POST /v1/me/link-sleeper's
      // docstring for why this step exists).
      await api.linkSleeperUsername(clean);

      if (result.leagues.length === 1) {
        const only = result.leagues[0];
        const saved = await api.saveLeague({ leagueId: only.league_id, sleeperUsername: clean, leagueName: only.name, makeDefault: true });
        if (finishSave(saved)) {
          // once_key scoped by leagueId (trackFeatureUse's default dedupe),
          // matching app.py's set_selected_league: once_key=selected_league_id.
          trackFeatureUse("league_import_completed", { leagueId: only.league_id });
          setStatus("idle");
          continueAfterSave(saved, only.league_id, only.name);
        }
        return;
      }

      setLeagues(result.leagues);
      setSelected(defaultLeagueSelection(result.leagues));
      setStatus("idle");
    } catch (error) {
      setStatus("error");
      if (isConnectivityFailure(error)) {
        setConnectError(describeSleeperConnectError({ status: "network", username: clean }));
      } else {
        setMessage(error instanceof Error ? error.message : "Something went wrong.");
      }
      trackFeatureUse("league_import_failed", { dedupe: false, props: { reason: "exception" } });
    }
  };

  // Saves every checked league, newest season first. The first that saves opens; the plan's cap never blocks the ones that did.
  const connectSelected = async () => {
    const plan = planSaves(selected, leagues);
    if (plan.length === 0) return;
    setStatus("saving");
    setMessage(null);
    const outcomes: SaveOutcome[] = [];
    for (const { league } of plan) {
      try {
        const saved = await api.saveLeague({ leagueId: league.league_id, sleeperUsername: username.trim(), leagueName: league.name });
        if (isSaveFailure(saved)) {
          outcomes.push({ leagueId: league.league_id, leagueName: league.name, ok: false, reason: saved?.reason || "unavailable" });
          trackFeatureUse("league_import_failed", { dedupe: false, props: { reason: saved?.reason || "unavailable" } });
        } else {
          outcomes.push({ leagueId: league.league_id, leagueName: league.name, ok: true, warming: Boolean(saved?.warming) });
          trackFeatureUse("league_import_completed", { leagueId: league.league_id });
        }
      } catch (error) {
        outcomes.push({ leagueId: league.league_id, leagueName: league.name, ok: false, reason: error instanceof Error ? error.message : "exception" });
        trackFeatureUse("league_import_failed", { dedupe: false, props: { reason: "exception" } });
      }
    }
    const summary = summarizeSaves(outcomes);
    setStatus("idle");
    if (summary.atCap) {
      setAtCap({ open: summary.open ? { leagueId: summary.open.leagueId, leagueName: summary.open.leagueName } : null });
      return;
    }
    if (!summary.open) {
      setStatus("error");
      const reason = summary.failedReason ?? "";
      setMessage(reason && reason !== "exception" && !reason.includes(" ") ? saveFailureMessage(reason) : reason || "Could not open that league.");
      return;
    }
    continueAfterSave({ ok: true, reason: "", cap: 0, warming: summary.open.warming } as SaveLeagueResponse, summary.open.leagueId, summary.open.leagueName);
  };

  if (atCap) {
    return (
      <div className="flex flex-col gap-3">
        <PremiumUpsellCard bare kicker="Saved leagues" upsell={LEAGUE_CAP_UPSELL} fallbackTitle={LEAGUE_CAP_UPSELL.title} fallbackBody={LEAGUE_CAP_UPSELL.body} />
        {atCap.open ? (
          <Button onClick={() => onLeagueChosen(atCap.open!.leagueId, atCap.open!.leagueName)}>Continue to {atCap.open.leagueName}</Button>
        ) : null}
      </div>
    );
  }

  if (warming) {
    return <LeagueWarmupProgress leagueId={warming.leagueId} onDone={() => onLeagueChosen(warming.leagueId, warming.name)} />;
  }

  if (leagues.length > 0) {
    // A continuing dynasty league gets a brand-new league_id every season it
    // rolls over on Sleeper, so the SAME league can legitimately appear twice
    // (once per season). Grouped by season, newest first, under a visible
    // year header so the wrong year's league is never picked by mistake.
    const groups = groupLeaguesBySeason(leagues);
    return (
      <div className="flex flex-col gap-3 motion-in" data-motion="in" data-testid="league-picker">
        <h2 style={{ font: "var(--font-card-title)" }}>
          Found {leagues.length} leagues for {username.trim()}
        </h2>
        {groups.map((group) => (
          <div key={group.season} className="flex flex-col gap-2">
            <span className="text-xs font-bold uppercase tracking-wide" style={{ color: "var(--color-text-muted)" }}>
              {group.season} season
            </span>
            {group.leagues.map((league) => {
              const on = selected.includes(league.league_id);
              return (
                <button
                  key={league.league_id}
                  type="button"
                  role="checkbox"
                  aria-checked={on}
                  aria-label={`${league.name}, ${leagueMeta(league)}`}
                  onClick={() => setSelected((current) => toggleLeague(current, league.league_id))}
                  className="glass-surface flex items-center gap-3 px-3 py-2 text-left"
                  style={{
                    minHeight: "var(--touch-target-min)",
                    color: "var(--color-text-primary)",
                    borderLeft: on ? "var(--border-width-semantic) solid var(--color-accent)" : undefined,
                  }}
                >
                  <TeamAvatar avatarUrl={league.avatar_url} name={league.name} size={36} />
                  <span className="min-w-0 flex-1">
                    <span className="block font-bold">{league.name}</span>
                    <span className="block text-xs" style={{ color: "var(--color-text-muted)" }}>
                      {leagueMeta(league)}
                    </span>
                  </span>
                  <span
                    aria-hidden="true"
                    className="flex shrink-0 items-center justify-center font-bold"
                    style={{
                      width: 22,
                      height: 22,
                      borderRadius: "var(--radius-control)",
                      border: "1px solid var(--color-border)",
                      background: on ? "var(--color-accent)" : "transparent",
                      color: "var(--color-on-accent)",
                    }}
                  >
                    {on ? "✓" : ""}
                  </span>
                </button>
              );
            })}
          </div>
        ))}
        {message ? (
          <p role="alert" className="m-0 text-xs" style={{ color: "var(--color-warning)" }}>
            {message}
          </p>
        ) : null}
        <Button type="button" onClick={() => void connectSelected()} disabled={selected.length === 0} loading={status === "saving"} data-testid="connect-selected">
          {connectCtaLabel(selected.length)}
        </Button>
        <p className="m-0 text-xs" style={{ color: "var(--color-text-muted)" }}>
          {CONNECT_TRUST_LINE}
        </p>
      </div>
    );
  }

  const loading = status === "loading";
  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3">
      <label className="flex flex-col gap-1 text-sm">
        {CONNECT_FIELD_LABEL}
        <Input value={username} onChange={(event) => setUsername(event.target.value)} placeholder={CONNECT_PLACEHOLDER} autoCapitalize="none" autoCorrect="off" />
      </label>
      <Button type="submit" loading={loading}>
        {CONNECT_PRIMARY_LABEL}
      </Button>
      <p className="m-0 text-xs" style={{ color: "var(--color-text-muted)" }}>
        {CONNECT_TRUST_LINE}
      </p>
      {loading ? (
        // Skeleton identity: the list that is about to appear, not a "Loading..." line.
        <div aria-busy="true" data-testid="connect-skeleton">
          <SkeletonRows count={2} />
        </div>
      ) : null}
      {connectError && connectError.kind === "network" ? (
        <ErrorState bare message={connectError.message} onRetry={() => void handleSubmit()} />
      ) : connectError ? (
        <div role="alert" className="flex flex-col gap-2 text-xs">
          <EmptyState title={connectError.message} subtitle={connectError.hint || undefined} icon={undefined} accent="var(--color-warning)" />
          {connectError.offerSleeperSignup ? (
            <p className="m-0" style={{ color: "var(--color-text-secondary)" }}>
              Don&apos;t have a Sleeper account?{" "}
              <a href="https://sleeper.com" target="_blank" rel="noreferrer" className="font-bold underline" style={{ color: "var(--color-accent)" }}>
                Create a free one at sleeper.com
              </a>
              , join or start a league, then come back here.
            </p>
          ) : null}
          {connectError.offerSample && !sampleCtaBelow ? <SampleLeagueButton surface="connect_error" /> : null}
          <HelpLink context={{ topic: "connect_error", platform: "sleeper", detail: connectError.message }} />
        </div>
      ) : message ? (
        <div role="alert" className="flex flex-col gap-1 text-xs" style={{ color: "var(--color-warning)" }}>
          <p className="m-0">{message}</p>
        </div>
      ) : null}
      <div className="flex flex-col gap-1">
        <button type="button" aria-expanded={whatIsOpen} onClick={() => setWhatIsOpen(!whatIsOpen)} className="tap-link self-start text-xs font-bold" style={{ color: "var(--color-text-secondary)", minHeight: "var(--touch-target-min)" }}>
          What is Sleeper? {whatIsOpen ? "−" : "+"}
        </button>
        {whatIsOpen ? (
          <div className="glass-input flex flex-col gap-1 px-3 py-3 text-xs motion-in" data-motion="in" style={{ borderLeft: "var(--border-width-semantic) solid var(--color-accent)", color: "var(--color-text-secondary)" }}>
            <p className="m-0">{CONNECT_WHAT_IS_SLEEPER}</p>
            <p className="m-0">
              Don&apos;t have a Sleeper league yet?{" "}
              <a href="https://sleeper.com" target="_blank" rel="noreferrer" className="font-bold underline" style={{ color: "var(--color-accent)" }}>
                Create a free one at sleeper.com
              </a>
              .
            </p>
          </div>
        ) : null}
      </div>
    </form>
  );
}
