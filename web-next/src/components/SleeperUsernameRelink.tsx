"use client";

import { useState } from "react";

import { Button } from "@/components/Button";
import { Input } from "@/components/Input";
import { api } from "@/lib/api";
import { describeSleeperConnectError, isConnectivityFailure } from "@/lib/sleeperConnectErrors";

/**
 * Change or link the Sleeper username on the account. Same two calls as
 * SleeperImportForm (lookupSleeperLeagues to verify the user and their
 * leagues, then linkSleeperUsername) and the same error copy; mirrors
 * mobile's More > Change Sleeper username.
 */
export function SleeperUsernameRelink({
  current,
  onLinked,
}: {
  current: string;
  onLinked: (username: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [username, setUsername] = useState(current);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!open) {
    return (
      <Button
        variant="secondary"
        size="sm"
        onClick={() => {
          setUsername(current);
          setError(null);
          setOpen(true);
        }}
      >
        {current ? "Change Sleeper username" : "Link Sleeper username"}
      </Button>
    );
  }

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    const clean = username.trim();
    if (!clean) return;
    setBusy(true);
    setError(null);
    try {
      const lookup = await api.lookupSleeperLeagues(clean);
      if (!lookup.ok || lookup.leagues.length === 0) {
        const described = describeSleeperConnectError({
          status: lookup.ok ? "no_leagues" : lookup.status,
          username: clean,
          serverMessage: lookup.message,
        });
        setError(`${described.message} ${described.hint}`.trim());
        return;
      }
      const linked = await api.linkSleeperUsername(clean);
      if (!linked.ok) {
        setError("Could not update your Sleeper username right now. Please try again in a moment.");
        return;
      }
      onLinked(linked.sleeper_username ?? clean);
      setOpen(false);
    } catch (err) {
      setError(
        isConnectivityFailure(err)
          ? describeSleeperConnectError({ status: "network", username: clean }).message
          : err instanceof Error
            ? err.message
            : "Could not update your Sleeper username right now.",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <form onSubmit={submit} className="flex flex-col gap-2">
      <label className="flex flex-col gap-1 text-xs" style={{ color: "var(--color-text-secondary)" }}>
        Use your Sleeper username, not your display name or email.
        <Input
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          placeholder="Sleeper username"
          autoCapitalize="none"
          autoCorrect="off"
          aria-label="Sleeper username"
        />
      </label>
      {error ? (
        <p role="alert" className="text-xs" style={{ color: "var(--color-danger)" }}>
          {error}
        </p>
      ) : null}
      <div className="flex items-center gap-2">
        <Button type="submit" size="sm" loading={busy} disabled={!username.trim()}>
          {busy ? "Checking…" : "Save"}
        </Button>
        <Button type="button" variant="secondary" size="sm" disabled={busy} onClick={() => setOpen(false)}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
