"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { api, type CollegeProspectsResponse } from "@/lib/api";
import { CollegeScoutingContent } from "@/components/CollegeScoutingContent";

// Like Portfolio/News/Trade History, College Scouting has no [leagueId]
// segment — the real current page (modules/college_scouting_ui.py) and GET
// /v1/scouting/prospects both read the same shared prospect pool regardless
// of which league is selected (every signed-in user grades the same
// catalog). Mobile's CollegeProspectsScreen.tsx is the same: no leagueId
// param anywhere in the call.
export default function CollegeScoutingPage() {
  const router = useRouter();
  const { session, loading: authLoading } = useAuth();

  const [data, setData] = useState<CollegeProspectsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!session) {
      router.replace("/");
      return;
    }
    let cancelled = false;

    api
      .getCollegeProspects()
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load College Scouting.");
      });

    return () => {
      cancelled = true;
    };
  }, [authLoading, session, router]);

  if (authLoading || (!data && !error)) {
    return (
      <main className="flex-1 flex items-center justify-center">
        <p style={{ color: "var(--color-text-muted)" }}>Loading College Scouting…</p>
      </main>
    );
  }

  if (error || !data) {
    return (
      <main className="flex-1 flex items-center justify-center px-4">
        <p role="alert" style={{ color: "var(--color-danger)" }}>
          {error || "Could not load College Scouting."}
        </p>
      </main>
    );
  }

  return <CollegeScoutingContent data={data} />;
}
