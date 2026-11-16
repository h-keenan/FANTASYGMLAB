"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect } from "react";

import { LoadingScreen } from "@/components/LoadingScreen";
import { retiredRouteTarget, type RetiredLeagueSegment } from "@/lib/retiredRoutes";
import { useSearchParams } from "@/lib/useSearchParams";

/**
 * The body of a retired league route (/alerts, /live-draft, /league-recaps): it only forwards to the tab/section that
 * absorbed the page (lib/retiredRoutes.ts), so a stale bookmark, push deep link or shared URL still lands somewhere real.
 */
export function RetiredLeagueRoute({ segment, label, layout }: { segment: RetiredLeagueSegment; label: string; layout: "dashboard" | "list" | "detail" }) {
  const params = useParams<{ leagueId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const leagueId = decodeURIComponent(params.leagueId);
  const target = retiredRouteTarget(segment, leagueId, searchParams);
  useEffect(() => {
    router.replace(target);
  }, [target, router]);
  return <LoadingScreen label={label} layout={layout} />;
}
