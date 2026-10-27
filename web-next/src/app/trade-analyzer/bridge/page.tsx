"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { LoadingScreen } from "@/components/LoadingScreen";
import { useAuth } from "@/context/AuthContext";
import { maskSavedLeagueRows } from "@/lib/privacy";
import { storeCurrentPathForReturnAfterSignIn } from "@/lib/protectedRouteReturn";
import { supabase } from "@/lib/supabase";
import { analyzerBridgePath, bridgeTradeFromSearch } from "@/lib/tradeBridge";

interface SavedLeague {
  league_id: string;
  league_name: string | null;
}

/**
 * League picker for a trade carried over from the public Trade Analyzer
 * (?a=&b=) when the signed-in user has more than one league: the trade is
 * applied inside whichever league they choose. With one league, or none
 * usable, it routes straight on.
 */
export default function TradeAnalyzerBridgePage() {
  const router = useRouter();
  const { session, loading } = useAuth();
  const [leagues, setLeagues] = useState<SavedLeague[] | null>(null);
  const [trade] = useState(() =>
    typeof window === "undefined" ? null : bridgeTradeFromSearch(window.location.search),
  );

  useEffect(() => {
    if (loading) return;
    if (!session) {
      storeCurrentPathForReturnAfterSignIn();
      router.replace("/");
      return;
    }
    if (!trade) {
      router.replace("/portfolio");
      return;
    }
    let cancelled = false;
    supabase
      .from("saved_leagues")
      .select("league_id, league_name")
      .then(({ data }) => {
        if (cancelled) return;
        const rows = maskSavedLeagueRows((data ?? []) as SavedLeague[]);
        if (rows.length === 1) {
          router.replace(analyzerBridgePath(rows[0].league_id, rows[0].league_name || rows[0].league_id, trade));
        } else if (rows.length === 0) {
          router.replace("/connect-league");
        } else {
          setLeagues(rows);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [loading, session, trade, router]);

  if (loading || !session || !trade || !leagues) return <LoadingScreen />;

  return (
    <main className="flex-1 flex flex-col items-center px-4 py-12 gap-6">
      <div className="w-full max-w-sm flex flex-col gap-1 text-center">
        <h1 style={{ font: "var(--font-page-title)" }}>Which league is this trade for?</h1>
        <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
          We&apos;ll load your trade into that league&apos;s analyzer and check it against your roster.
        </p>
      </div>
      <ul className="w-full max-w-sm flex flex-col gap-2">
        {leagues.map((league) => {
          const name = league.league_name || league.league_id;
          return (
            <li key={league.league_id}>
              <Link
                href={analyzerBridgePath(league.league_id, name, trade)}
                className="glass-surface flex items-center justify-between px-4 text-sm font-bold"
                style={{ minHeight: "var(--touch-target-min)", color: "inherit", textDecoration: "none" }}
              >
                <span>{name}</span>
                <span aria-hidden="true" style={{ color: "var(--color-accent)" }}>
                  →
                </span>
              </Link>
            </li>
          );
        })}
      </ul>
    </main>
  );
}
