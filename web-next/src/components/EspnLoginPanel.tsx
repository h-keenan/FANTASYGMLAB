"use client";

import { useState } from "react";

import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import { api } from "@/lib/api";
import { ESPN_COOKIE_STEPS, ESPN_LOGIN_WHY, espnCredentialFailureMessage } from "@/lib/leaguePlatform";

/**
 * Connect an ESPN login (espn_s2 + SWID) so private ESPN leagues can be read.
 * The values go to POST /v1/espn/credentials and are never shown back. With a
 * league id + season the server proves the login on that league first, so a
 * typo is caught here ("test on your league") rather than as an empty league.
 */
export function EspnLoginPanel({
  leagueId,
  season,
  onConnected,
}: {
  leagueId?: string;
  season?: number;
  onConnected: () => void;
}) {
  const [espnS2, setEspnS2] = useState("");
  const [swid, setSwid] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!espnS2.trim() || !swid.trim()) {
      setMessage("Paste both espn_s2 and SWID.");
      return;
    }
    setBusy(true);
    setMessage(null);
    try {
      const result = await api.saveEspnCredentials({ espnS2, swid, leagueId, season });
      if (!result?.ok) {
        setMessage(espnCredentialFailureMessage(result));
        return;
      }
      // Drop the cookie values from state as soon as they're saved.
      setEspnS2("");
      setSwid("");
      onConnected();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="flex flex-col gap-3" aria-label="Connect your ESPN login">
      <div
        className="glass-input flex flex-col gap-2 px-3 py-3 text-xs"
        style={{ borderLeft: "var(--border-width-semantic) solid var(--color-accent)", color: "var(--color-text-secondary)" }}
      >
        <p className="m-0 font-bold" style={{ color: "var(--color-text-primary)" }}>
          This league is private. Connect your ESPN login to read it.
        </p>
        <p className="m-0">{ESPN_LOGIN_WHY}</p>
        <details>
          <summary className="cursor-pointer font-bold" style={{ color: "var(--color-accent)" }}>
            How to find espn_s2 and SWID
          </summary>
          <ol className="m-0 mt-2 pl-4 flex flex-col gap-1">
            {ESPN_COOKIE_STEPS.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
        </details>
      </div>
      <label className="flex flex-col gap-1 text-sm">
        espn_s2
        <Input type="password" value={espnS2} onChange={(e) => setEspnS2(e.target.value)} autoComplete="off" spellCheck={false} />
      </label>
      <label className="flex flex-col gap-1 text-sm">
        SWID
        <Input
          value={swid}
          onChange={(e) => setSwid(e.target.value)}
          placeholder="{XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX}"
          autoComplete="off"
          spellCheck={false}
        />
      </label>
      {message ? (
        <p role="alert" className="m-0 text-xs" style={{ color: "var(--color-warning)" }}>
          {message}
        </p>
      ) : null}
      <Button type="submit" loading={busy}>
        {busy ? "Testing on your league…" : leagueId ? "Test on my league and connect" : "Save ESPN login"}
      </Button>
    </form>
  );
}

/** One line: "ESPN login connected" + Remove. Renders nothing until a login is saved. */
export function EspnLoginStatus({ saved, onRemoved }: { saved: boolean; onRemoved: () => void }) {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  if (!saved) return null;
  const remove = async () => {
    setBusy(true);
    setMessage(null);
    try {
      const result = await api.deleteEspnCredentials();
      if (result?.ok) onRemoved();
      else setMessage(espnCredentialFailureMessage(result));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Something went wrong.");
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="flex flex-wrap items-center gap-2 text-xs" style={{ color: "var(--color-text-secondary)" }}>
      <span>ESPN login connected (private leagues can load).</span>
      <button type="button" onClick={remove} disabled={busy} className="font-bold" style={{ color: "var(--color-accent)" }}>
        {busy ? "Removing…" : "Remove"}
      </button>
      {message ? (
        <span role="alert" style={{ color: "var(--color-warning)" }}>
          {message}
        </span>
      ) : null}
    </div>
  );
}
