"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/context/AuthContext";
import { api, type NewsResponse } from "@/lib/api";
import { NewsContent } from "@/components/NewsContent";

// Like Portfolio, News has no [leagueId] segment — GET /v1/news is a
// general, non-roster-scoped feed for anyone, not "your team's" news (see
// that endpoint's own docstring in services/mobile_api_service.py).
export default function NewsPage() {
  const router = useRouter();
  const { session, loading: authLoading } = useAuth();

  const [data, setData] = useState<NewsResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!session) {
      router.replace("/");
      return;
    }
    let cancelled = false;

    api
      .getNews()
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Could not load News.");
      });

    return () => {
      cancelled = true;
    };
  }, [authLoading, session, router]);

  if (authLoading || (!data && !error)) {
    return (
      <main className="flex-1 flex items-center justify-center">
        <p style={{ color: "var(--color-text-muted)" }}>Loading News…</p>
      </main>
    );
  }

  if (error || !data) {
    return (
      <main className="flex-1 flex items-center justify-center px-4">
        <p role="alert" style={{ color: "var(--color-danger)" }}>
          {error || "Could not load News."}
        </p>
      </main>
    );
  }

  return <NewsContent data={data} />;
}
