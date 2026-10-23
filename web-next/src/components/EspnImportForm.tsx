"use client";

import { useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { trackFeatureUse, trackUse } from "@/lib/analytics";
import { api, type EspnLeaguePreviewResponse } from "@/lib/api";
import { ESPN_PRIVATE_LEAGUE_HINT, espnImportFailureResult, espnSeasonOptions } from "@/lib/leaguePlatform";

const SAVE_FAILURE_COPY: Record<string, string> = {
  at_cap: "Your plan's saved-league limit is reached. Upgrade to Premium to add another league.",
  league_not_found: "ESPN didn't return that league just now. Please try again.",
  espn_team_not_selected: "Pick which team is yours first.",
  mapping_too_low: "Too few of this league's players matched FantasyDesk's player list to value it accurately.",
};

/**
 * ESPN half of the Connect League flow (SleeperImportForm's platform
 * choice). Public ESPN leagues only: the user enters the league ID and
 * season, sees what loaded (teams, how many players matched FantasyDesk's
 * player list, which features work for ESPN leagues today), picks their own
 * team, and saves. ESPN has no username lookup for public leagues, so the
 * team pick is how "my roster" is known later.
 *
 * Private leagues would need the user's espn_s2/SWID cookies stored on our
 * server, so they're out of scope and this form never asks for them.
 */
export function EspnImportForm({ onLeagueChosen }: { onLeagueChosen: (leagueId: string, leagueName: string) => void }) {
  const { signInAsGuest, session } = useAuth();
  const seasons = espnSeasonOptions();
  const [leagueId, setLeagueId] = useState("");
  const [season, setSeason] = useState(seasons[0]);
  const [status, setStatus] = useState<"idle" | "loading" | "saving">("idle");
  const [message, setMessage] = useState<string | null>(null);
  const [preview, setPreview] = useState<EspnLeaguePreviewResponse | null>(null);
  const [rosterId, setRosterId] = useState("");
  const [isPrivate, setIsPrivate] = useState(false);

  const handleSubmit = async (event?: React.FormEvent) => {
    event?.preventDefault();
    const clean = leagueId.trim();
    if (!/^\d{1,12}$/.test(clean)) {
      setMessage("Enter your ESPN league ID. It's the number after leagueId= in your ESPN league's web address.");
      return;
    }
    setStatus("loading");
    setMessage(null);
    setIsPrivate(false);
    setPreview(null);
    setRosterId("");
    trackFeatureUse("league_import_started", { props: { platform: "espn" } });
    try {
      if (!session) {
        const { error } = await signInAsGuest();
        if (error) {
          setStatus("idle");
          setMessage(error);
          return;
        }
      }
      const result = await api.previewEspnLeague(clean, season);
      setStatus("idle");
      if (!result.league) {
        setIsPrivate(result.reason === "private_league");
        setMessage(result.reason === "private_league" ? ESPN_PRIVATE_LEAGUE_HINT : result.message || "That ESPN league couldn't be loaded.");
        trackUse("league_import", "failed", { props: { result: espnImportFailureResult(result.reason) } });
        trackFeatureUse("league_import_failed", { dedupe: false, props: { platform: "espn", reason: result.reason || "unavailable" } });
        return;
      }
      setPreview(result);
      if (!result.ok) {
        setMessage(result.message);
        trackFeatureUse("league_import_failed", { dedupe: false, props: { platform: "espn", reason: result.reason || "unavailable" } });
      }
    } catch (error) {
      setStatus("idle");
      setMessage(error instanceof Error ? error.message : "Something went wrong.");
      trackUse("league_import", "failed", { props: { result: "espn_error" } });
      trackFeatureUse("league_import_failed", { dedupe: false, props: { platform: "espn", reason: "exception" } });
    }
  };

  const saveLeague = async () => {
    if (!preview?.league || !rosterId) return;
    const { league_key: key, name } = preview.league;
    setStatus("saving");
    setMessage(null);
    try {
      const result = await api.saveLeague({ leagueId: key, leagueName: name, rosterId, makeDefault: true });
      if (!result.ok) {
        setStatus("idle");
        setMessage(SAVE_FAILURE_COPY[result.reason] || "Could not save that league right now. Please try again in a moment.");
        trackFeatureUse("league_import_failed", { dedupe: false, props: { platform: "espn", reason: result.reason || "unavailable" } });
        return;
      }
      trackFeatureUse("league_import_completed", { leagueId: key, props: { platform: "espn" } });
      setStatus("idle");
      onLeagueChosen(key, name);
    } catch (error) {
      setStatus("idle");
      setMessage(error instanceof Error ? error.message : "Could not save that league.");
      trackFeatureUse("league_import_failed", { dedupe: false, props: { platform: "espn", reason: "exception" } });
    }
  };

  if (preview?.league) {
    const diagnostics = preview.diagnostics;
    const matchedPercent = diagnostics ? Math.round(diagnostics.matched_rate * 100) : 0;
    const available = (preview.features ?? []).filter((item) => item.status === "available");
    const unavailable = (preview.features ?? []).filter((item) => item.status !== "available");
    return (
      <div className="flex flex-col gap-3">
        <div className="flex flex-col gap-1">
          <h2 style={{ font: "var(--font-card-title)" }}>{preview.league.name}</h2>
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            ESPN · {preview.league.season} season · {preview.league.team_count} teams
          </span>
        </div>
        {diagnostics ? (
          <p className="m-0 text-xs" style={{ color: "var(--color-text-secondary)" }}>
            {diagnostics.canonical_matched_count} of {diagnostics.total_espn_players_seen} rostered players matched
            FantasyDesk&apos;s player list ({matchedPercent}%). Team defenses (D/ST) and players we don&apos;t track yet
            aren&apos;t valued.
          </p>
        ) : null}
        {preview.ok ? (
          <>
            <span className="text-xs font-bold uppercase tracking-wide" style={{ color: "var(--color-text-muted)" }}>
              Which team is yours?
            </span>
            <div className="flex flex-col gap-2" role="radiogroup" aria-label="Your ESPN team">
              {(preview.teams ?? []).map((team) => {
                const selected = team.roster_id === rosterId;
                return (
                  <button
                    key={team.roster_id}
                    type="button"
                    role="radio"
                    aria-checked={selected}
                    onClick={() => setRosterId(team.roster_id)}
                    className="glass-surface text-left px-4 py-3"
                    style={{
                      color: "var(--color-text-primary)",
                      borderLeft: selected ? "var(--border-width-semantic) solid var(--color-accent)" : undefined,
                    }}
                  >
                    <span className="block font-bold">{team.team_name}</span>
                    <span className="block text-xs" style={{ color: "var(--color-text-muted)" }}>
                      {team.owner_name}
                    </span>
                  </button>
                );
              })}
            </div>
          </>
        ) : null}
        <div className="glass-input flex flex-col gap-1 px-3 py-3 text-xs" style={{ color: "var(--color-text-secondary)" }}>
          <p className="m-0">
            <strong>Works for ESPN leagues:</strong> {available.map((item) => item.feature).join(", ")}.
          </p>
          <p className="m-0">
            <strong>Not available for ESPN leagues yet:</strong> {unavailable.map((item) => item.feature).join(", ")}.
          </p>
        </div>
        {message ? (
          <p role="alert" className="m-0 text-xs" style={{ color: "var(--color-warning)" }}>
            {message}
          </p>
        ) : null}
        <div className="flex items-center gap-3">
          {preview.ok ? (
            <button
              type="button"
              onClick={saveLeague}
              disabled={!rosterId || status === "saving"}
              className="px-4 py-2 text-sm font-bold"
              style={{
                background: "var(--color-accent-strong)",
                color: "var(--color-brand-mark-ink)",
                fontWeight: "var(--font-weight-button)",
                opacity: !rosterId || status === "saving" ? "var(--opacity-disabled)" : 1,
              }}
            >
              {status === "saving" ? "Saving…" : "Add this league"}
            </button>
          ) : null}
          <button
            type="button"
            onClick={() => {
              setPreview(null);
              setMessage(null);
              setRosterId("");
            }}
            className="text-xs font-bold"
            style={{ color: "var(--color-text-muted)" }}
          >
            Use a different league
          </button>
        </div>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3">
      <div
        className="glass-input flex flex-col gap-1 px-3 py-3 text-xs"
        style={{
          borderLeft: "var(--border-width-semantic) solid var(--color-accent)",
          color: "var(--color-text-secondary)",
        }}
      >
        <p className="m-0">
          FantasyDesk can read <strong>public</strong> ESPN leagues. Your league ID is the number after{" "}
          <code>leagueId=</code> in your ESPN league&apos;s web address.
        </p>
        <p className="m-0">
          Private ESPN leagues aren&apos;t supported yet. Your league manager can make the league viewable to the public in
          ESPN&apos;s league settings.
        </p>
      </div>
      <label className="flex flex-col gap-1 text-sm">
        ESPN league ID
        <input
          value={leagueId}
          onChange={(event) => setLeagueId(event.target.value)}
          placeholder="e.g. 12345678"
          inputMode="numeric"
          autoComplete="off"
          className="glass-input px-3 py-2"
          style={{ color: "var(--color-text-primary)" }}
        />
      </label>
      <label className="flex flex-col gap-1 text-sm">
        Season
        <select
          value={season}
          onChange={(event) => setSeason(Number(event.target.value))}
          className="glass-input px-3 py-2"
          style={{ color: "var(--color-text-primary)" }}
        >
          {seasons.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </select>
      </label>
      {message ? (
        <p role="alert" className="m-0 text-xs" style={{ color: "var(--color-warning)" }}>
          {message}
        </p>
      ) : null}
      {isPrivate ? (
        <button
          type="button"
          onClick={() => void handleSubmit()}
          disabled={status === "loading"}
          className="text-xs font-bold self-start"
          style={{ color: "var(--color-accent)" }}
        >
          Retry
        </button>
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
        {status === "loading" ? "Loading league from ESPN…" : "Find my ESPN league"}
      </button>
    </form>
  );
}
