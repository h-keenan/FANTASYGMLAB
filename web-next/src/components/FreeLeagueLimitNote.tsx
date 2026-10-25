"use client";

import { useEffect, useState } from "react";

import { FreeLimitNote } from "@/components/FreeLimitNote";
import { api } from "@/lib/api";
import { supabase } from "@/lib/supabase";

/**
 * "Free: 1 of 1 league" on the Add a league page, before the user picks a
 * league and is told no. The cap is the server's (GET /v1/me league_cap);
 * the count is the user's saved_leagues rows. Renders nothing until both are
 * known, and for Premium or an unreadable plan (profile_status "error").
 */
export function FreeLeagueLimitNote() {
  const [state, setState] = useState<{ cap: number; used: number; isPremium: boolean | null } | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.getMe(), supabase.from("saved_leagues").select("league_id")])
      .then(([me, saved]) => {
        if (cancelled || saved.error) return;
        const user = me.user;
        setState({
          cap: user.league_cap,
          used: (saved.data ?? []).length,
          isPremium: user.profile_status === "ok" ? user.entitlement === "premium" : null,
        });
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  if (!state) return null;
  return (
    <FreeLimitNote
      kind="cap"
      noun={state.cap === 1 ? "league" : "leagues"}
      limit={state.cap}
      used={state.used}
      isPremium={state.isPremium}
    />
  );
}
