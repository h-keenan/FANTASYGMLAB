"use client";

import { useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { Button } from "@/components/Button";
import { Input } from "@/components/Input";

/**
 * P0 UX audit (2026-10-27): mobile already has a full forgot-password flow
 * (mobile/src/screens/LoginScreen.tsx) but a password-reset email always
 * lands on the web app (Supabase's recovery link follows the project's
 * default Site URL, not a per-platform redirect — see AuthContext's
 * resetPassword comment). Before this, that link just silently signed the
 * browser into a session with no prompt to set a new password — the
 * completion UI this used to rely on was modules/account_ui.py's Streamlit
 * app, deleted long ago (see modules/auth_supabase.py's now-orphaned
 * request_password_reset / *_recovery_pending helpers).
 *
 * Mounted once at the root layout (inside AuthProvider, alongside every
 * other page) so it catches the recovery link regardless of which path it
 * happens to land on. Blocking by design — a scrim with no close button —
 * because the session Supabase just created is only valid for setting a
 * new password; "Cancel and sign out" is the only way out besides finishing.
 */
export function PasswordRecoveryGate() {
  const { recoveryPending, completeRecovery, signOut } = useAuth();
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (!recoveryPending) return null;

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (password !== confirmPassword) {
      setError("Passwords don't match.");
      return;
    }
    setBusy(true);
    setError(null);
    const result = await completeRecovery(password);
    setBusy(false);
    if (result.error) setError(result.error);
  };

  return (
    <div
      className="fixed inset-0 flex items-center justify-center p-4"
      style={{ background: "var(--color-scrim)", zIndex: 100 }}
    >
      <div className="glass-surface flex w-full max-w-sm flex-col gap-4 p-6">
        <div className="flex flex-col gap-0.5">
          <h2 className="text-lg font-extrabold" style={{ color: "var(--color-text-primary)" }}>
            Set a new password
          </h2>
          <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
            Choose a new password (6+ characters) to finish resetting it.
          </p>
        </div>
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <label className="flex flex-col gap-1 text-sm" style={{ color: "var(--color-text-secondary)" }}>
            New password
            <Input
              type="password"
              required
              autoFocus
              minLength={6}
              autoComplete="new-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </label>
          <label className="flex flex-col gap-1 text-sm" style={{ color: "var(--color-text-secondary)" }}>
            Confirm new password
            <Input
              type="password"
              required
              minLength={6}
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
            />
          </label>
          {error ? (
            <p role="alert" className="text-xs" style={{ color: "var(--color-danger)" }}>
              {error}
            </p>
          ) : null}
          <Button type="submit" loading={busy}>
            {busy ? "Saving…" : "Set new password"}
          </Button>
          <Button
            type="button"
            variant="ghost"
            onClick={() => {
              void signOut();
            }}
          >
            Cancel and sign out
          </Button>
        </form>
      </div>
    </div>
  );
}
