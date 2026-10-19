"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { api, type MeResponse, type PushCategory } from "@/lib/api";
import { AccountContent } from "@/components/AccountContent";
import { ErrorState } from "@/components/ErrorState";
import { LoadingScreen } from "@/components/LoadingScreen";

/**
 * Account/Settings (coridian_, 2026-10-19) — the single place to see "this
 * is your account": identity (GET /v1/me, already returned everywhere else
 * but never shown as a readable summary), billing (the existing
 * /v1/billing/portal session, same one Premium's "Manage Billing" already
 * opens), Community Trade Feed opt-out + push notification category
 * toggles (both backed by the existing user_settings-keyed endpoints — no
 * new preference invented here), and account actions (sign out, GDPR data
 * export, delete account via the same `delete_user` Supabase RPC mobile's
 * MoreScreen already calls).
 *
 * No `[leagueId]` segment — same single-page shape as Premium/Portfolio,
 * since an account applies across every league, not one.
 */
export default function AccountPage() {
  const router = useRouter();
  const { session, loading: authLoading, signOut, deleteAccount } = useAuth();

  const [me, setMe] = useState<MeResponse | null>(null);
  const [communityOptedOut, setCommunityOptedOut] = useState(false);
  // null = not loaded yet (or the fetch failed) — AccountContent hides the
  // whole Push notifications block in that case rather than showing it
  // with wrong/empty toggles. Not load-blocking for the rest of the page
  // (fetched in a separate, non-awaited call below) since it's the one
  // genuinely new preference surface this page adds.
  const [pushCategories, setPushCategories] = useState<Record<PushCategory, boolean> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [retryToken, setRetryToken] = useState(0);

  useEffect(() => {
    if (authLoading) return;
    if (!session) {
      router.replace("/");
      return;
    }
    let cancelled = false;

    Promise.all([api.getMe(), api.getCommunityPreferences()])
      .then(([meResult, communityResult]) => {
        if (cancelled) return;
        setMe(meResult);
        setCommunityOptedOut(communityResult.opted_out);
        setError(null);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load your account.");
      });

    api
      .getPushPreferences()
      .then((result) => {
        if (!cancelled) setPushCategories(result.categories);
      })
      .catch(() => {
        // Fail soft — see the pushCategories comment above.
      });

    return () => {
      cancelled = true;
    };
  }, [authLoading, session, router, retryToken]);

  const handleToggleCommunityOptOut = useCallback((next: boolean) => {
    setCommunityOptedOut(next);
    return api.updateCommunityPreferences(next).catch(() => {
      // Revert on failure so the toggle never silently lies about state.
      setCommunityOptedOut(!next);
    });
  }, []);

  const handleTogglePushCategory = useCallback((category: PushCategory, enabled: boolean) => {
    setPushCategories((current) => (current ? { ...current, [category]: enabled } : current));
    return api.updatePushPreference(category, enabled).catch(() => {
      setPushCategories((current) => (current ? { ...current, [category]: !enabled } : current));
    });
  }, []);

  const handleOpenBillingPortal = useCallback(async () => {
    const result = await api.openBillingPortal();
    window.location.href = result.portal_url;
  }, []);

  const handleExportData = useCallback(async () => {
    const result = await api.exportMyData();
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `fantasydesk-data-export-${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
  }, []);

  const handleDeleteAccount = useCallback(async () => {
    const { error: deleteError } = await deleteAccount();
    if (deleteError) throw new Error(deleteError);
    router.replace("/");
  }, [deleteAccount, router]);

  const handleSignOut = useCallback(() => {
    void signOut().then(() => router.replace("/"));
  }, [signOut, router]);

  if (authLoading || (!me && !error)) {
    return <LoadingScreen status="Loading your account…" />;
  }

  if (error || !me) {
    return (
      <ErrorState
        message={error || "Could not load your account."}
        onRetry={() => {
          setError(null);
          setRetryToken((token) => token + 1);
        }}
      />
    );
  }

  return (
    <AccountContent
      user={me.user}
      communityOptedOut={communityOptedOut}
      onToggleCommunityOptOut={handleToggleCommunityOptOut}
      pushCategories={pushCategories}
      onTogglePushCategory={handleTogglePushCategory}
      onOpenBillingPortal={handleOpenBillingPortal}
      onExportData={handleExportData}
      onDeleteAccount={handleDeleteAccount}
      onSignOut={handleSignOut}
    />
  );
}
