"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { api, type PortfolioResponse } from "@/lib/api";
import { PortfolioContent } from "@/components/PortfolioContent";
import { LoadingScreen } from "@/components/LoadingScreen";

// Unlike every other ported page, Portfolio has no [leagueId] segment — it
// spans every one of the signed-in account's saved leagues at once (see
// modules/portfolio_page.py / GET /v1/portfolio's own docstrings).
export default function PortfolioPage() {
  const router = useRouter();
  const { session, loading: authLoading } = useAuth();

  const [data, setData] = useState<PortfolioResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!session) {
      router.replace("/");
      return;
    }
    let cancelled = false;

    api
      .getPortfolio()
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load Portfolio.");
      });

    return () => {
      cancelled = true;
    };
  }, [authLoading, session, router]);

  if (authLoading || (!data && !error)) {
    return (
      <LoadingScreen status="Loading Portfolio…" />
    );
  }

  if (error || !data) {
    return (
      <main className="flex-1 flex items-center justify-center px-4">
        <p role="alert" style={{ color: "var(--color-danger)" }}>
          {error || "Could not load Portfolio."}
        </p>
      </main>
    );
  }

  return <PortfolioContent data={data} />;
}
