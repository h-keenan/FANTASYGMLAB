"use client";

import { useState } from "react";

import { api, type SleeperLeagueSummary } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";
import { trackFeatureUse } from "@/lib/analytics";

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
export function SleeperImportForm({ onLeagueChosen }: { onLeagueChosen: (leagueId: string, leagueName: string) => void }) {
  const { signInAsGuest, session } = useAuth();
  const [username, setUsername] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [message, setMessage] = useState<string | null>(null);
  // Distinguishes "that username has a typo" from "I don't have a Sleeper
  // account at all" — the API's plain message text only covers the first
  // case ("Check spelling and try again"), which left a genuinely new-to-
  // Sleeper user with no path forward (see onboarding audit, 2026-10-18).
  const [noSleeperAccount, setNoSleeperAccount] = useState(false);
  const [leagues, setLeagues] = useState<SleeperLeagueSummary[]>([]);

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    const clean = username.trim();
    if (!clean) return;

    setStatus("loading");
    setMessage(null);
    setNoSleeperAccount(false);
    setLeagues([]);
    // Mirrors app.py's load_leagues_for_username, which fires this on every
    // lookup attempt (once per session) regardless of outcome -- this is
    // the "attempted a Sleeper connect" signal, not "succeeded".
    trackFeatureUse("league_import_started");

    try {
      if (!session) {
        const { error } = await signInAsGuest();
        if (error) {
          setStatus("error");
          setMessage(error);
          return;
        }
      }

      const result = await api.lookupSleeperLeagues(clean);
      if (result.ok) {
        // Mirrors app.py: the username itself resolved on Sleeper's side
        // (even a zero-leagues account counts here, same as lookup.status
        // "ok" or "no_leagues" there) -- this is identity resolution, not
        // league selection, so it fires before the leagues.length check.
        trackFeatureUse("sleeper_connected");
      }
      if (!result.ok || result.leagues.length === 0) {
        setStatus("error");
        setNoSleeperAccount(result.status === "user_not_found");
        setMessage(result.message || "No eligible leagues found for that username.");
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
        await api.saveLeague({ leagueId: only.league_id, sleeperUsername: clean, leagueName: only.name, makeDefault: true });
        // once_key scoped by leagueId (trackFeatureUse's default dedupe),
        // matching app.py's set_selected_league: once_key=selected_league_id.
        trackFeatureUse("league_import_completed", { leagueId: only.league_id });
        setStatus("idle");
        onLeagueChosen(only.league_id, only.name);
        return;
      }

      setLeagues(result.leagues);
      setStatus("idle");
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Something went wrong.");
      trackFeatureUse("league_import_failed", { dedupe: false, props: { reason: "exception" } });
    }
  };

  const openLeague = async (league: SleeperLeagueSummary) => {
    setStatus("loading");
    try {
      await api.saveLeague({ leagueId: league.league_id, sleeperUsername: username.trim(), leagueName: league.name });
      trackFeatureUse("league_import_completed", { leagueId: league.league_id });
      setStatus("idle");
      onLeagueChosen(league.league_id, league.name);
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : "Could not open that league.");
      trackFeatureUse("league_import_failed", { dedupe: false, props: { reason: "exception" } });
    }
  };

  if (leagues.length > 0) {
    // Bug report, 2026-10-21: "it keeps auto defaulting to 2025" / "we need
    // to be able to separate by year" — a continuing dynasty league gets a
    // brand-new league_id every season it rolls over on Sleeper's side, so
    // the SAME league can legitimately appear here twice (once per season).
    // A flat list made it easy to tap the wrong year's card for "the same"
    // league. Grouping by season under a visible year header, most recent
    // season first, makes the distinction impossible to miss.
    const seasons = Array.from(new Set(leagues.map((league) => league.season))).sort(
      (a, b) => Number(b) - Number(a),
    );
    return (
      <div className="flex flex-col gap-3">
        <h2 style={{ font: "var(--font-card-title)" }}>Choose a league</h2>
        {seasons.map((season) => (
          <div key={season} className="flex flex-col gap-2">
            <span
              className="text-xs font-bold uppercase tracking-wide"
              style={{ color: "var(--color-text-muted)" }}
            >
              {season} season
            </span>
            {leagues
              .filter((league) => league.season === season)
              .map((league) => (
                <button
                  key={league.league_id}
                  onClick={() => openLeague(league)}
                  className="glass-surface text-left px-4 py-3 flex items-center justify-between"
                  style={{ color: "var(--color-text-primary)" }}
                >
                  <span>
                    <span className="block font-bold">{league.name}</span>
                    <span className="block text-xs" style={{ color: "var(--color-text-muted)" }}>
                      {league.season} · {league.total_rosters} teams
                    </span>
                  </span>
                  <span style={{ color: "var(--color-accent)" }}>Open league →</span>
                </button>
              ))}
          </div>
        ))}
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3">
      {/* Onboarding audit, 2026-10-18: a new user hit the Sleeper username
          field with zero prior explanation of what Sleeper is or that an
          existing account there is required — the landing page sells the
          product's value but never mentions the dependency. */}
      <div
        className="glass-input flex flex-col gap-1 px-3 py-3 text-xs"
        style={{
          borderLeft: "var(--border-width-semantic) solid var(--color-accent)",
          color: "var(--color-text-secondary)",
        }}
      >
        <p className="m-0">
          FantasyDesk connects to your existing <strong>Sleeper</strong> fantasy league — it reads your real roster,
          matchups, and league settings to build recommendations.
        </p>
        <p className="m-0">
          Don&apos;t have a Sleeper league yet?{" "}
          <a
            href="https://sleeper.com"
            target="_blank"
            rel="noreferrer"
            className="font-bold underline"
            style={{ color: "var(--color-accent)" }}
          >
            Create a free one at sleeper.com
          </a>
          .
        </p>
      </div>
      <label className="flex flex-col gap-1 text-sm">
        Sleeper username
        <input
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          placeholder="Sleeper username"
          className="glass-input px-3 py-2"
          style={{ color: "var(--color-text-primary)" }}
        />
      </label>
      {message ? (
        <div role="alert" className="flex flex-col gap-1 text-xs" style={{ color: "var(--color-warning)" }}>
          <p className="m-0">{message}</p>
          {noSleeperAccount ? (
            <p className="m-0" style={{ color: "var(--color-text-secondary)" }}>
              Don&apos;t have a Sleeper account?{" "}
              <a
                href="https://sleeper.com"
                target="_blank"
                rel="noreferrer"
                className="font-bold underline"
                style={{ color: "var(--color-accent)" }}
              >
                Create a free one at sleeper.com
              </a>
              , join or start a league, then come back here.
            </p>
          ) : null}
        </div>
      ) : null}
      <button
        type="submit"
        disabled={status === "loading"}
        className="px-4 py-2 text-sm font-bold self-start"
        style={{
          background: "var(--color-accent-strong)",
          color: "var(--color-brand-mark-ink)",
          fontWeight: "var(--font-weight-button)",
          opacity: status === "loading" ? "var(--opacity-disabled)" : 1,
        }}
      >
        {status === "loading" ? "Loading leagues from Sleeper…" : "Load my leagues"}
      </button>
    </form>
  );
}
