"use client";

import { useCallback, useEffect, useState } from "react";

import { Button } from "@/components/Button";
import { SkeletonRows } from "@/components/Skeleton";
import { useAuth } from "@/context/AuthContext";
import { trackFeatureUse } from "@/lib/analytics";
import { api, type YahooLeagueOption } from "@/lib/api";
import {
  YAHOO_CONNECT_LABEL,
  YAHOO_NO_LEAGUES,
  YAHOO_PICK_HEADING,
  YAHOO_UNAVAILABLE,
  YAHOO_WHY,
  parseYahooReturn,
  yahooNeedsConnect,
  yahooReasonMessage,
} from "@/lib/yahooConnect";

type Phase = "checking" | "unavailable" | "connect" | "loading" | "pick";

/**
 * Yahoo half of the Connect League flow (EspnImportForm platform="yahoo"). Yahoo has no league-ID lookup: the user signs
 * in with Yahoo (OAuth, full-page redirect through the API callback), comes back to /connect-league?yahoo=connected, and
 * picks a league from their own list. `onPick` hands the chosen league key to the shared preview -> team -> save flow.
 */
export function YahooConnectStep({ onPick, disabled }: { onPick: (league: YahooLeagueOption) => void; disabled?: boolean }) {
  const { session, signInAsGuest } = useAuth();
  const [loadedPhase, setPhase] = useState<Phase>("checking");
  // A failed Yahoo round trip (?yahoo=error&yahoo_reason=...) is shown once, on arrival.
  const [message, setMessage] = useState<string | null>(() => {
    const returned = typeof window === "undefined" ? null : parseYahooReturn(window.location.search);
    return returned && !returned.connected ? yahooReasonMessage(returned.reason) : null;
  });
  const [leagues, setLeagues] = useState<YahooLeagueOption[]>([]);
  const [busy, setBusy] = useState(false);
  // No session yet (landing, signed out): nothing to look up, go straight to Connect (which starts a guest session).
  const phase: Phase = session ? loadedPhase : "connect";

  const loadLeagues = useCallback(async () => {
    setPhase("loading");
    try {
      const result = await api.listYahooLeagues();
      if (!result.ok) {
        setMessage(yahooReasonMessage(result.reason, result.message));
        setPhase(yahooNeedsConnect(result.reason) ? "connect" : "pick");
        setLeagues([]);
        return;
      }
      setLeagues(result.leagues ?? []);
      setPhase("pick");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : yahooReasonMessage("yahoo_unavailable"));
      setPhase("pick");
    }
  }, []);

  useEffect(() => {
    if (!session) return;
    let live = true;
    api
      .getYahooStatus()
      .then((status) => {
        if (!live) return;
        if (!status.ok || !status.available) {
          setPhase("unavailable");
        } else if (status.connected) {
          void loadLeagues();
        } else {
          setPhase("connect");
        }
      })
      .catch(() => live && setPhase("unavailable"));
    return () => {
      live = false;
    };
  }, [session, loadLeagues]);

  const connect = async () => {
    setBusy(true);
    setMessage(null);
    trackFeatureUse("league_import_started", { props: { platform: "yahoo" } });
    try {
      if (!session) {
        const { error } = await signInAsGuest();
        if (error) {
          setMessage(error);
          setBusy(false);
          return;
        }
      }
      const result = await api.startYahooOAuth("web");
      if (!result.ok || !result.authorize_url) {
        setMessage(yahooReasonMessage(result.reason, result.message));
        setBusy(false);
        return;
      }
      window.location.assign(result.authorize_url);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : yahooReasonMessage("yahoo_unavailable"));
      setBusy(false);
    }
  };

  const disconnect = async () => {
    setBusy(true);
    try {
      const result = await api.disconnectYahoo();
      if (result.ok) {
        setLeagues([]);
        setPhase("connect");
        setMessage(null);
      } else {
        setMessage(yahooReasonMessage(result.reason, result.message));
      }
    } finally {
      setBusy(false);
    }
  };

  if (phase === "checking" || phase === "loading") {
    return (
      <div role="status" aria-label="Checking your Yahoo account" data-testid="yahoo-skeleton">
        <SkeletonRows count={2} />
      </div>
    );
  }

  if (phase === "unavailable") {
    return (
      <p role="alert" className="m-0 text-xs" style={{ color: "var(--color-warning)" }}>
        {YAHOO_UNAVAILABLE}
      </p>
    );
  }

  if (phase === "connect") {
    return (
      <div className="flex flex-col gap-3" data-testid="yahoo-connect">
        <p className="m-0 text-xs" style={{ color: "var(--color-text-secondary)" }}>
          {YAHOO_WHY}
        </p>
        {message ? (
          <p role="alert" className="m-0 text-xs" style={{ color: "var(--color-warning)" }}>
            {message}
          </p>
        ) : null}
        <Button type="button" onClick={() => void connect()} loading={busy} disabled={disabled}>
          {YAHOO_CONNECT_LABEL}
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-3" data-testid="yahoo-leagues">
      <span className="text-xs font-bold uppercase tracking-wide" style={{ color: "var(--color-text-muted)" }}>
        {YAHOO_PICK_HEADING}
      </span>
      {message ? (
        <p role="alert" className="m-0 text-xs" style={{ color: "var(--color-warning)" }}>
          {message}
        </p>
      ) : null}
      {leagues.length === 0 && !message ? (
        <p className="m-0 text-xs" style={{ color: "var(--color-text-secondary)" }}>
          {YAHOO_NO_LEAGUES}
        </p>
      ) : null}
      <div className="flex flex-col gap-2">
        {leagues.map((league) => (
          <button
            key={league.league_key}
            type="button"
            disabled={disabled}
            onClick={() => onPick(league)}
            className="glass-surface text-left px-4 py-3"
            style={{ color: "var(--color-text-primary)" }}
          >
            <span className="block font-bold">{league.name}</span>
            <span className="block text-xs" style={{ color: "var(--color-text-muted)" }}>
              {league.season} season · {league.team_count} teams
            </span>
          </button>
        ))}
      </div>
      <button
        type="button"
        onClick={() => void disconnect()}
        disabled={busy}
        className="text-xs font-bold self-start"
        style={{ color: "var(--color-text-muted)" }}
      >
        Disconnect Yahoo
      </button>
    </div>
  );
}
