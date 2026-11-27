"use client";

import { useEffect, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { trackFeatureUse, trackUse } from "@/lib/analytics";
import { api, type EspnLeaguePreviewResponse, type YahooLeagueOption } from "@/lib/api";
import { ESPN_PRIVATE_HELP_STEPS, ESPN_PRIVATE_LEAGUE_HINT, espnImportFailureResult, espnSeasonOptions } from "@/lib/leaguePlatform";
import { Button } from "@/components/Button";
import { PremiumUpsellCard } from "@/components/PremiumUpsellCard";
import { LEAGUE_CAP_UPSELL, saveFailureMessage } from "@/lib/leagueSave";
import { Input } from "@/components/Input";
import { PillRow } from "@/components/PillRow";
import { TeamAvatar } from "@/components/TeamAvatar";
import { IMPORT_STEP_ORDER, importStepProgress, importStepTitle, type ImportStepKey } from "@/lib/connectFlow";
import { SampleLeagueButton } from "@/components/SampleLeagueBanner";
import { EspnLoginPanel, EspnLoginStatus } from "@/components/EspnLoginPanel";
import { ErrorState } from "@/components/ErrorState";
import { YahooConnectStep } from "@/components/YahooConnectStep";
import { yahooReasonMessage } from "@/lib/yahooConnect";
import { connectPlatformNotice } from "@/lib/connectFlow";

export type ImportPlatform = "espn" | "fleaflicker" | "mfl" | "yahoo";

/** Per-platform copy. Everything else about the flow is shared. */
const PLATFORM_COPY: Record<
  ImportPlatform,
  { label: string; idHelp: React.ReactNode; privateNote: string; notFound: string; placeholder: string; findLabel: string }
> = {
  espn: {
    label: "ESPN",
    idHelp: (
      <>
        Your league ID is the number after <code>leagueId=</code> in your ESPN league&apos;s web address.
      </>
    ),
    privateNote:
      "Public league: just the ID. Private league: we'll ask you to connect your ESPN login (stored encrypted), only if needed.",
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
  yahoo: {
    label: "Yahoo",
    idHelp: <>Sign in with Yahoo and pick your league from your own list. No league ID needed.</>,
    privateNote: "Read-only. Yahoo leagues are private, so FantasyDesk reads them with your Yahoo sign-in.",
    notFound: "Pick one of your Yahoo leagues.",
    placeholder: "",
    findLabel: "Find my Yahoo league",
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

/** The platform's help copy (where to find the ID, what is private, what is not supported yet). Shown behind the step header's info icon. */
export function PlatformHelp({ platform }: { platform: ImportPlatform }) {
  const copy = PLATFORM_COPY[platform];
  return (
    <>
      <p className="m-0" data-testid="platform-notice">
        {connectPlatformNotice(copy.label)}
      </p>
      <p className="m-0">{copy.idHelp}</p>
      <p className="m-0">{copy.privateNote}</p>
    </>
  );
}

/**
 * ESPN half of the Connect League flow (SleeperImportForm's platform
 * choice). Public ESPN leagues only: the user enters the league ID and
 * season, sees what loaded (teams, how many players matched FantasyDesk's
 * player list, which features work for ESPN leagues today), picks their own
 * team, and saves. ESPN has no username lookup for public leagues, so the
 * team pick is how "my roster" is known later.
 *
 * Private leagues: when the preview says `private_league` and the server can
 * store a login (`can_connect`), EspnLoginPanel asks for espn_s2/SWID, proves
 * them on this league, and the preview is retried. Nothing asks for them up front.
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
  const [canConnect, setCanConnect] = useState(false);
  const [loginSaved, setLoginSaved] = useState(false);
  // The ID step comes first; the season step runs the lookup; the team step is the preview.
  const [formStep, setFormStep] = useState<"id" | "season">("id");

  // Whether an ESPN login is already saved, so the user sees (and can remove) it.
  useEffect(() => {
    if (platform !== "espn" || !session) return;
    let live = true;
    api
      .getEspnCredentialStatus()
      .then((result) => {
        if (live && result?.ok) setLoginSaved(Boolean(result.saved));
      })
      .catch(() => {});
    return () => {
      live = false;
    };
  }, [platform, session]);

  /** Yahoo: the user already picked a league from their own list (no league-ID field). */
  const pickYahooLeague = async (league: YahooLeagueOption) => {
    setStatus("loading");
    setMessage(null);
    setPreview(null);
    setRosterId("");
    trackFeatureUse("league_import_started", { props: { platform } });
    try {
      const result = await api.previewYahooLeague(league.league_key);
      setStatus("idle");
      if (!result.league) {
        setMessage(yahooReasonMessage(result.reason, result.message));
        trackFeatureUse("league_import_failed", { dedupe: false, props: { platform, reason: result.reason || "unavailable" } });
        return;
      }
      setPreview(result);
      if (!result.ok) setMessage(result.message);
    } catch (error) {
      setStatus("idle");
      setMessage(error instanceof Error ? error.message : "Something went wrong.");
      trackFeatureUse("league_import_failed", { dedupe: false, props: { platform, reason: "exception" } });
    }
  };

  const handleSubmit = async (event?: React.FormEvent) => {
    event?.preventDefault();
    if (platform === "yahoo") return; // Yahoo has no ID form: pickYahooLeague handles it
    const clean = leagueId.trim();
    if (!/^\d{1,12}$/.test(clean)) {
      setMessage(copy.notFound);
      return;
    }
    setStatus("loading");
    setMessage(null);
    setIsPrivate(false);
    setCanConnect(false);
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
        setCanConnect(espnPrivate && Boolean(result.can_connect));
        setMessage(espnPrivate && result.can_connect ? null : espnPrivate ? ESPN_PRIVATE_LEAGUE_HINT : result.message || `That ${copy.label} league couldn't be loaded.`);
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
        {platform !== "yahoo" ? <StepProgress step="team" /> : null}
        <div className="flex flex-col gap-1">
          <h2 style={{ font: "var(--font-card-title)" }}>{preview.league.name}</h2>
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            {copy.label} · {preview.league.season} season · {preview.league.team_count} teams
          </span>
        </div>
        {preview.ok ? (
          <>
            <span className="text-xs font-bold uppercase tracking-wide" style={{ color: "var(--color-text-muted)" }}>
              {importStepTitle("team", copy.label)}
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
                    className="glass-surface flex items-center gap-3 px-3 py-2 text-left"
                    style={{
                      minHeight: "var(--touch-target-min)",
                      color: "var(--color-text-primary)",
                      borderLeft: selected ? "var(--border-width-semantic) solid var(--color-accent)" : undefined,
                    }}
                  >
                    <TeamAvatar name={team.team_name} size={36} />
                    <span className="min-w-0 flex-1">
                      <span className="block font-bold">{team.team_name}</span>
                      <span className="block text-xs" style={{ color: "var(--color-text-muted)" }}>
                        {team.owner_name}
                      </span>
                    </span>
                    <span
                      aria-hidden="true"
                      className="flex shrink-0 items-center justify-center font-bold"
                      style={{
                        width: 22,
                        height: 22,
                        borderRadius: "50%",
                        border: "1px solid var(--color-border)",
                        background: selected ? "var(--color-accent)" : "transparent",
                        color: "var(--color-on-accent)",
                      }}
                    >
                      {selected ? "✓" : ""}
                    </span>
                  </button>
                );
              })}
            </div>
          </>
        ) : null}
        {/* Match details: open when the import was refused (that explanation IS the answer), tucked away when it worked. */}
        <details open={!preview.ok} className="glass-input flex flex-col gap-1 px-3 py-3 text-xs" style={{ color: "var(--color-text-secondary)" }}>
          <summary className="cursor-pointer font-bold" style={{ color: "var(--color-text-primary)" }}>
            Match details
          </summary>
          <div className="mt-2 flex flex-col gap-1">
            {diagnostics ? (
              <p className="m-0">
                {diagnostics.canonical_matched_count} of {diagnostics.total_espn_players_seen ?? diagnostics.total_players_seen} rostered players matched
                FantasyDesk&apos;s player list ({matchedPercent}%). Team defenses (D/ST) and players we don&apos;t track yet
                aren&apos;t valued.
              </p>
            ) : null}
            {diagnostics?.unmapped_players?.length ? (
              <p className="m-0">
                <strong>Left off rosters (no confident match):</strong>{" "}
                {diagnostics.unmapped_players
                  .slice(0, 12)
                  .map((player) => `${player.name}${player.position ? ` (${player.position})` : ""}`)
                  .join(", ")}
                {diagnostics.unmapped_players.length > 12 ? `, +${diagnostics.unmapped_players.length - 12} more` : ""}.
              </p>
            ) : null}
            <p className="m-0">
              <strong>Works for {copy.label} leagues:</strong> {available.map((item) => item.feature).join(", ")}.
            </p>
            <p className="m-0">
              <strong>Not available for {copy.label} leagues yet:</strong> {unavailable.map((item) => item.feature).join(", ")}.
            </p>
          </div>
        </details>
        {message ? (
          <p role="alert" className="m-0 text-xs" style={{ color: "var(--color-warning)" }}>
            {message}
          </p>
        ) : null}
        <div className="flex items-center gap-3">
          {preview.ok ? (
            <Button type="button" onClick={saveLeague} disabled={!rosterId} loading={status === "saving"} style={{ alignSelf: "auto" }}>
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
            style={{ color: "var(--color-text-muted)", minHeight: "var(--touch-target-min)" }}
          >
            Use a different league
          </button>
        </div>
      </div>
    );
  }

  if (canConnect) {
    return (
      <div className="flex flex-col gap-3">
        <EspnLoginPanel
          leagueId={leagueId.trim()}
          season={season}
          onConnected={() => {
            setLoginSaved(true);
            setCanConnect(false);
            void handleSubmit();
          }}
        />
        <button type="button" onClick={() => setCanConnect(false)} className="text-xs font-bold self-start" style={{ color: "var(--color-text-muted)" }}>
          Use a different league
        </button>
      </div>
    );
  }

  if (platform === "yahoo") {
    return (
      <div className="flex flex-col gap-3">
        {message ? (
          <p role="alert" className="m-0 text-xs" style={{ color: "var(--color-warning)" }}>
            {message}
          </p>
        ) : null}
        <YahooConnectStep onPick={(league) => void pickYahooLeague(league)} disabled={status === "loading"} />
      </div>
    );
  }

  const goToSeason = () => {
    if (!/^\d{1,12}$/.test(leagueId.trim())) {
      setMessage(copy.notFound);
      return;
    }
    setMessage(null);
    setFormStep("season");
  };

  if (formStep === "id") {
    return (
      <form
        onSubmit={(event) => {
          event.preventDefault();
          goToSeason();
        }}
        className="flex flex-col gap-3"
      >
        <StepProgress step="id" />
        <label className="flex flex-col gap-1 text-sm">
          {importStepTitle("id", copy.label)}
          <Input
            value={leagueId}
            onChange={(event) => setLeagueId(event.target.value)}
            placeholder={copy.placeholder}
            inputMode="numeric"
            autoComplete="off"
          />
        </label>
        {message ? (
          <p role="alert" className="m-0 text-xs" style={{ color: "var(--color-warning)" }}>
            {message}
          </p>
        ) : null}
        <Button type="submit">Next</Button>
      </form>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-3">
      <StepProgress step="season" />
      <div className="flex flex-col gap-1 text-sm">
        <span id="import-season-label">{importStepTitle("season", copy.label)}</span>
        <PillRow
          ariaLabel={`${copy.label} season`}
          variant="fill"
          options={seasons.map((option) => ({ label: String(option), value: String(option) }))}
          active={String(season)}
          onSelect={(value) => setSeason(Number(value))}
        />
      </div>
      {platform === "espn" ? <EspnLoginStatus saved={loginSaved} onRemoved={() => setLoginSaved(false)} /> : null}
      {message ? (
        <p role="alert" className="m-0 text-xs" style={{ color: "var(--color-warning)" }}>
          {message}
        </p>
      ) : null}
      {isPrivate && !canConnect ? (
        <ol className="m-0 flex list-decimal flex-col gap-1 pl-5 text-xs" data-testid="espn-private-help" style={{ color: "var(--color-text-secondary)" }}>
          {ESPN_PRIVATE_HELP_STEPS.map((step) => (
            <li key={step}>{step}</li>
          ))}
        </ol>
      ) : null}
      {isPrivate && !canConnect ? <SampleLeagueButton surface="connect_error" variant="secondary" /> : null}
      {isPrivate ? (
        <button
          type="button"
          onClick={() => void handleSubmit()}
          disabled={status === "loading"}
          className="text-xs font-bold self-start"
          style={{ color: "var(--color-accent)", minHeight: "var(--touch-target-min)" }}
        >
          Try again
        </button>
      ) : null}
      <Button type="submit" disabled={status === "loading"}>
        {status === "loading" ? `Loading league from ${copy.label}…` : copy.findLabel}
      </Button>
      <button
        type="button"
        onClick={() => {
          setFormStep("id");
          setMessage(null);
        }}
        className="text-xs font-bold self-start"
        style={{ color: "var(--color-text-muted)", minHeight: "var(--touch-target-min)" }}
      >
        Change league ID
      </button>
    </form>
  );
}

/** "Step 2 of 3" with three dots: the platform stepper's position. */
function StepProgress({ step }: { step: ImportStepKey }) {
  return (
    <div className="flex items-center gap-2" data-testid="import-step-progress">
      <span className="text-xs font-bold uppercase tracking-wide" style={{ color: "var(--color-text-muted)" }}>
        {importStepProgress(step)}
      </span>
      <span aria-hidden="true" className="flex items-center gap-1">
        {IMPORT_STEP_ORDER.map((key) => (
          <span
            key={key}
            style={{
              width: 6,
              height: 6,
              borderRadius: "50%",
              background: key === step ? "var(--color-accent)" : "var(--color-border)",
            }}
          />
        ))}
      </span>
    </div>
  );
}
