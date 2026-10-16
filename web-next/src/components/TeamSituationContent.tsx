"use client";

import { useMemo, useState } from "react";

import { api, TEAM_STANCE_OPTIONS, type GmTarget, type MyTeamResponse, type TeamStance, type TeamStanceResponse } from "@/lib/api";
import { OvrGauge } from "@/components/OvrGauge";
import { PillRow } from "@/components/PillRow";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { PlayerIdentityTrigger } from "@/components/PlayerIdentityTrigger";
import { PositionBadge } from "@/components/PositionBadge";
import { buildProtectRows, splitProtectRows, type ProtectRow } from "@/lib/teamStancePresentation";
import { injuryTone } from "@/lib/myTeamPresentation";

/**
 * Ports modules/team_stance_ui.py / mobile's TeamStanceScreen.tsx for
 * Revision 19 — a small, standalone GM_TOOLS-adjacent page (Decision Memory
 * v1 gap, #232): declare a fixed stance (Rebuilding/Competing/Balanced),
 * plus a "Protected Players" checklist that reads/writes the SAME
 * untouchable flag GM Targets already owns (modules.gm_targets) rather than
 * a second, parallel protect list. On web it's reachable from the
 * Streamlit profile panel only (app.py's `_open_team_stance` button); this
 * page links out from GM Plan's Team Situation badge instead, since
 * web-next has no profile/settings surface of its own yet.
 *
 * Copy note: Streamlit's own supporting copy caveats the real valuation
 * effect as "in the mobile app" only, because app.py computes its own
 * valuation via a separate override (modules.profile.strategy_override)
 * that never reads this table. This page is NOT on that code path — like
 * mobile, it's backed by services/mobile_api_service.py, which already
 * feeds the declared stance into the same real age-curve/pick-value math
 * for Trade Hub, GM Plan, and Dashboard (see
 * `_fetch_gm_stance_with_set_flag`'s callers). So this page uses mobile's
 * uncaveated copy, not Streamlit's.
 */

const SUPPORTING_COPY =
  "Tell us how you see this team right now. We'll lean trade-idea language toward that stance, and use it to shape your trade and lineup value adjustments too.";

function ProtectPlayerRow({
  row,
  busy,
  onToggle,
}: {
  row: ProtectRow;
  busy: boolean;
  onToggle: (playerId: string, next: boolean) => void;
}) {
  const { player, protected: isProtected } = row;
  const tone = injuryTone(player.injury_label);

  return (
    <div
      className="flex items-center gap-3 py-2"
      style={{ borderBottom: "var(--border-width-default) solid var(--color-border)" }}
    >
      <PlayerIdentityTrigger
        identity={{ ...player, sourceLabel: "Team Situation" }}
        className="flex-1 flex items-center gap-3 min-w-0"
      >
        <PositionBadge position={player.position} />
        <PlayerAvatar playerId={player.player_id} tier={player.tier} size={40} />
        <OvrGauge rating={player.overall_rating} size="sm" />
        <div className="flex-1 flex flex-col gap-0.5 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-bold truncate" style={{ color: "var(--color-text-primary)" }}>
              {player.name || "Unknown player"}
            </span>
            {player.injury_label ? (
              <span
                className="px-1 text-xs font-bold uppercase"
                style={{
                  color:
                    tone === "danger" ? "var(--color-danger)" : tone === "warning" ? "var(--color-warning)" : "var(--color-text-muted)",
                }}
              >
                {player.injury_label}
              </span>
            ) : null}
          </div>
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            {player.team || "FA"}
          </span>
        </div>
      </PlayerIdentityTrigger>
      <button
        type="button"
        disabled={busy}
        onClick={() => onToggle(player.player_id, !isProtected)}
        className="px-2 py-1 text-xs font-bold shrink-0"
        style={
          isProtected
            ? {
                background: "var(--color-premium)",
                color: "var(--color-brand-mark-ink)",
                border: "var(--border-width-default) solid var(--color-premium)",
              }
            : { color: "var(--color-text-secondary)", border: "var(--border-width-default) solid var(--color-border)" }
        }
      >
        {busy ? "…" : isProtected ? "Protected" : "Protect"}
      </button>
    </div>
  );
}

export function TeamSituationContent({
  leagueId,
  leagueName,
  teamStance,
  myTeam,
  targets,
}: {
  leagueId: string;
  leagueName: string;
  teamStance: TeamStanceResponse;
  myTeam: MyTeamResponse;
  targets: GmTarget[];
}) {
  const [stance, setStanceState] = useState<TeamStance | "">(teamStance.stance);
  const [trackedRows, setTrackedRows] = useState<GmTarget[]>(targets);
  const [busyPlayerId, setBusyPlayerId] = useState<string | null>(null);

  const rows = useMemo(
    () => buildProtectRows(myTeam.starters, myTeam.bench, trackedRows),
    [myTeam.starters, myTeam.bench, trackedRows],
  );
  const { protectedRows, otherRows } = useMemo(() => splitProtectRows(rows), [rows]);

  const onPickStance = (value: string) => {
    const next = value as TeamStance;
    if (next === stance) return;
    // Genuine optimistic update, result intentionally discarded — same
    // contract mobile's GmStanceContext.setStance uses: the UI must reflect
    // the new stance immediately, before the round-trip resolves.
    setStanceState(next);
    void api.setTeamStance(leagueId, next).catch(() => {});
  };

  const onToggleProtect = (playerId: string, next: boolean) => {
    setBusyPlayerId(playerId);
    const wasTracked = trackedRows.some((row) => row.player_id === playerId);
    const previous = trackedRows;
    // Optimistic: flip/insert the row locally first.
    setTrackedRows((prev) => {
      if (!wasTracked) {
        return [...prev, { player_id: playerId, source_surface: "team_stance", created_at: null, untouchable: next }];
      }
      return prev.map((row) => (row.player_id === playerId ? { ...row, untouchable: next } : row));
    });

    (async () => {
      try {
        // Reuses GM Targets' existing untouchable flag rather than a second
        // protect list — a player must be a GM Target row before it can be
        // marked untouchable, so protecting one not already watched adds it
        // first (source_surface identifies the surface it came from).
        if (next && !wasTracked) {
          const addResult = await api.addGmTarget(leagueId, playerId, "team_stance");
          if (!addResult.ok) throw new Error(addResult.reason || "not_available");
        }
        if (next || wasTracked) {
          const result = await api.setGmTargetUntouchable(leagueId, playerId, next);
          if (!result.ok) throw new Error(result.reason || "not_available");
        }
      } catch {
        setTrackedRows(previous);
      } finally {
        setBusyPlayerId(null);
      }
    })();
  };

  const selectedOption = TEAM_STANCE_OPTIONS.find((option) => option.value === stance);
  const noRoster = rows.length === 0;

  return (
    <main className="flex-1 flex flex-col gap-6 px-4 py-8 max-w-3xl w-full mx-auto">
      <header className="flex flex-col gap-1">
        <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          Team Situation
        </span>
        <h1 style={{ font: "var(--font-page-title)" }}>{leagueName}</h1>
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
          {SUPPORTING_COPY}
        </p>
      </header>

      <section className="flex flex-col gap-2">
        <PillRow
          options={TEAM_STANCE_OPTIONS.map((option) => ({ label: option.label, value: option.value }))}
          active={stance}
          onSelect={onPickStance}
        />
        {selectedOption ? (
          <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            {selectedOption.description}
          </p>
        ) : null}
      </section>

      <section className="flex flex-col gap-2">
        <h2 style={{ font: "var(--type-section-title)" }}>Protected Players</h2>
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          Mark players you don&apos;t want traded away. This is the same protection GM Targets&apos; untouchable flag
          uses — toggling it here or there shows up in both places.
        </p>

        {noRoster ? (
          <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
            No roster players found for this league.
          </p>
        ) : (
          <div
            className="flex flex-col px-3"
            style={{ background: "var(--color-surface-secondary)", border: "var(--border-width-default) solid var(--color-border)" }}
          >
            {protectedRows.map((row) => (
              <ProtectPlayerRow
                key={row.player.player_id}
                row={row}
                busy={busyPlayerId === row.player.player_id}
                onToggle={onToggleProtect}
              />
            ))}
            {protectedRows.length > 0 && otherRows.length > 0 ? (
              <h3
                className="text-xs font-bold uppercase pt-3"
                style={{ color: "var(--color-text-muted)", letterSpacing: "0.03em" }}
              >
                Rest of Roster
              </h3>
            ) : null}
            {otherRows.map((row) => (
              <ProtectPlayerRow
                key={row.player.player_id}
                row={row}
                busy={busyPlayerId === row.player.player_id}
                onToggle={onToggleProtect}
              />
            ))}
          </div>
        )}
      </section>
    </main>
  );
}
