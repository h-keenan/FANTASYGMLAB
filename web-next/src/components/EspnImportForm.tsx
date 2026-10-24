"use client";

import { useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { trackFeatureUse, trackUse } from "@/lib/analytics";
import { api, type EspnLeaguePreviewResponse } from "@/lib/api";
import { ESPN_PRIVATE_LEAGUE_HINT, espnImportFailureResult, espnSeasonOptions } from "@/lib/leaguePlatform";
import { Button } from "@/components/Button";
import { PremiumUpsellCard } from "@/components/PremiumUpsellCard";
import { LEAGUE_CAP_UPSELL, saveFailureMessage } from "@/lib/leagueSave";
import { Input, Select } from "@/components/Input";

export type ImportPlatform = "espn" | "fleaflicker" | "mfl";

/** Per-platform copy. Everything else about the flow is shared. */
const PLATFORM_COPY: Record<
  ImportPlatform,
  { label: string; idHelp: React.ReactNode; privateNote: string; notFound: string; placeholder: string; findLabel: string }
> = {
  espn: {
    label: "ESPN",
    idHelp: (
      <>
        FantasyDesk can read <strong>public</strong> ESPN leagues. Your league ID is the number after <code>leagueId=</code>{" "}
        in your ESPN league&apos;s web address.
      </>
    ),
    privateNote:
      "Private ESPN leagues aren't supported yet. Your league manager can make the league viewable to the public in ESPN's league settings.",
    notFound: "Enter your ESPN league ID. It's the number after leagueId= in your ESPN league's web address.",
    placeholder: "e.g. 12345678",
    findLabel: "Find my ESPN league",
  },
  fleaflicker: {
    label: "Fleaflicker",
    idHelp: (
      <>
        Your league ID is the number after <code>/leagues/</code> in your Fleaflicker league&apos;s web address.
      </>
    ),
    privateNote: "Leagues that aren't viewable to the public can't be read.",
    notFound: "Enter your Fleaflicker league ID. It's the number after /leagues/ in your league's web address.",
    placeholder: "e.g. 206154",
    findLabel: "Find my Fleaflicker league",
  },
  mfl: {
    label: "MFL",
    idHelp: (
      <>
        Your league ID is the number at the end of your MFL league&apos;s web address, like <code>/home/12345</code>.
      </>
    ),
    privateNote: "MFL leagues that need a login aren't supported yet.",
    notFound: "Enter your MFL league ID. It's the number at the end of your league's web address.",
    placeholder: "e.g. 10015",
    findLabel: "Find my MFL league",
  },
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
export function EspnImportForm({
  onLeagueChosen,
  platform = "espn",
}: {
  onLeagueChosen: (leagueId: string, leagueName: string) => void;
  platform?: ImportPlatform;
}) {
  const copy = PLATFORM_COPY[platform];
  const { signInAsGuest, session } = useAuth();
  const seasons = espnSeasonOptions();
  const [leagueId, setLeagueId] = useState("");
  const [season, setSeason] = useState(seasons[0]);
  const [status, setStatus] = useState<"idle" | "loading" | "saving">("idle");
  const [message, setMessage] = useState<string | null>(null);
  const [preview, setPreview] = useState<EspnLeaguePreviewResponse | null>(null);
  const [rosterId, setRosterId] = useState("");
  const [isPrivate, setIsPrivate] = useState(false);
  const [atCap, setAtCap] = useState(false);

  const handleSubmit = async (event?: React.FormEvent) => {
    event?.preventDefault();
    const clean = leagueId.trim();
    if (!/^\d{1,12}$/.test(clean)) {
      setMessage(copy.notFound);
      return;
    }
    setStatus("loading");
    setMessage(null);
    setIsPrivate(false);
    setPreview(null);
    setRosterId("");
    trackFeatureUse("league_import_started", { props: { platform } });
    try {
      if (!session) {
        const { error } = await signInAsGuest();
        if (error) {
          setStatus("idle");
          setMessage(error);
          return;
        }
      }
      const result =
        platform === "espn" ? await api.previewEspnLeague(clean, season) : await api.previewImportedLeague(platform, clean, season);
      setStatus("idle");
      if (!result.league) {
        const espnPrivate = platform === "espn" && result.reason === "private_league";
        setIsPrivate(espnPrivate);
        setMessage(espnPrivate ? ESPN_PRIVATE_LEAGUE_HINT : result.message || `That ${copy.label} league couldn't be loaded.`);
        if (platform === "espn") trackUse("league_import", "failed", { props: { result: espnImportFailureResult(result.reason) } });
        trackFeatureUse("league_import_failed", { dedupe: false, props: { platform, reason: result.reason || "unavailable" } });
        return;
      }
      setPreview(result);
      if (!result.ok) {
        setMessage(result.message);
        trackFeatureUse("league_import_failed", { dedupe: false, props: { platform, reason: result.reason || "unavailable" } });
      }
    } catch (error) {
      setStatus("idle");
      setMessage(error instanceof Error ? error.message : "Something went wrong.");
      if (platform === "espn") trackUse("league_import", "failed", { props: { result: "espn_error" } });
      trackFeatureUse("league_import_failed", { dedupe: false, props: { platform, reason: "exception" } });
    }
  };

  const saveLeague = async () => {
    if (!preview?.league || !rosterId) return;
    const { league_key: key, name } = preview.league;
    setStatus("saving");
    setMessage(null);
    try {
      const result = await api.saveLeague({ leagueId: key, leagueName: name, rosterId, makeDefault: true });
      if (!result?.ok) {
        setStatus("idle");
        if (result?.reason === "at_cap") {
          setAtCap(true);
        } else {
          setMessage(saveFailureMessage(result?.reason));
        }
        trackFeatureUse("league_import_failed", { dedupe: false, props: { platform, reason: result?.reason || "unavailable" } });
        return;
      }
      trackFeatureUse("league_import_completed", { leagueId: key, props: { platform } });
      setStatus("idle");
      onLeagueChosen(key, name);
    } catch (error) {
      setStatus("idle");
      setMessage(error instanceof Error ? error.message : "Could not save that league.");
      trackFeatureUse("league_import_failed", { dedupe: false, props: { platform, reason: "exception" } });
    }
  };

  if (atCap) {
    return (
      <PremiumUpsellCard bare kicker="Saved leagues" upsell={LEAGUE_CAP_UPSELL} fallbackTitle={LEAGUE_CAP_UPSELL.title} fallbackBody={LEAGUE_CAP_UPSELL.body} />
    );
  }

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
            {copy.label} · {preview.league.season} season · {preview.league.team_count} teams
          </span>
        </div>
        {diagnostics ? (
          <p className="m-0 text-xs" style={{ color: "var(--color-text-secondary)" }}>
            {diagnostics.canonical_matched_count} of {diagnostics.total_espn_players_seen ?? diagnostics.total_players_seen} rostered players matched
            FantasyDesk&apos;s player list ({matchedPercent}%). Team defenses (D/ST) and players we don&apos;t track yet
            aren&apos;t valued.
          </p>
        ) : null}
        {diagnostics?.unmapped_players?.length ? (
          <p className="m-0 text-xs" style={{ color: "var(--color-text-secondary)" }}>
            <strong>Left off rosters (no confident match):</strong>{" "}
            {diagnostics.unmapped_players
              .slice(0, 12)
              .map((player) => `${player.name}${player.position ? ` (${player.position})` : ""}`)
              .join(", ")}
            {diagnostics.unmapped_players.length > 12 ? `, +${diagnostics.unmapped_players.length - 12} more` : ""}.
          </p>
        ) : null}
        {preview.ok ? (
          <>
            <span className="text-xs font-bold uppercase tracking-wide" style={{ color: "var(--color-text-muted)" }}>
              Which team is yours?
            </span>
            <div className="flex flex-col gap-2" role="radiogroup" aria-label={`Your ${copy.label} team`}>
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
            <strong>Works for {copy.label} leagues:</strong> {available.map((item) => item.feature).join(", ")}.
          </p>
          <p className="m-0">
            <strong>Not available for {copy.label} leagues yet:</strong> {unavailable.map((item) => item.feature).join(", ")}.
          </p>
        </div>
        {message ? (
          <p role="alert" className="m-0 text-xs" style={{ color: "var(--color-warning)" }}>
            {message}
          </p>
        ) : null}
        <div className="flex items-center gap-3">
          {preview.ok ? (
            <Button
              type="button"
              onClick={saveLeague}
              disabled={!rosterId}
              loading={status === "saving"}
        style={{ alignSelf: "auto" }}
      >
              {status === "saving" ? "Saving…" : "Add this league"}
            </Button>
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
        <p className="m-0">{copy.idHelp}</p>
        <p className="m-0">{copy.privateNote}</p>
      </div>
      <label className="flex flex-col gap-1 text-sm">
        {copy.label} league ID
        <Input
          value={leagueId}
          onChange={(event) => setLeagueId(event.target.value)}
          placeholder={copy.placeholder}
          inputMode="numeric"
          autoComplete="off"
        />
      </label>
      <label className="flex flex-col gap-1 text-sm">
        Season
        <Select
          value={season}
          onChange={(event) => setSeason(Number(event.target.value))}
        >
          {seasons.map((option) => (
            <option key={option} value={option}>
              {option}
            </option>
          ))}
        </Select>
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
      <Button
        type="submit"
        disabled={status === "loading"}
      >
        {status === "loading" ? `Loading league from ${copy.label}…` : copy.findLabel}
      </Button>
    </form>
  );
}
