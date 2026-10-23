"use client";

import { useParams, useRouter } from "next/navigation";
import { useSearchParams } from "@/lib/useSearchParams";
import { useEffect } from "react";

import { LoadingScreen } from "@/components/LoadingScreen";

/**
 * Revision 20 (2026-10-18): GM Targets merged into GM Plan (see
 * GmPlanContent's own docstring) — this route now only exists so a stale
 * bookmark/link still lands somewhere real instead of a 404.
 */
export default function GmTargetsRedirectPage() {
  const params = useParams<{ leagueId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();

  const leagueId = decodeURIComponent(params.leagueId);
  const name = searchParams.get("name");

  useEffect(() => {
    router.replace(`/gm-plan/${encodeURIComponent(leagueId)}${name ? `?name=${encodeURIComponent(name)}` : ""}`);
  }, [leagueId, name, router]);

  return <LoadingScreen status="Redirecting to GM Plan…" />;
}
