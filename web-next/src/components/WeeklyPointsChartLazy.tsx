"use client";

import dynamic from "next/dynamic";
import { useEffect } from "react";

import { SkeletonBlock } from "@/components/Skeleton";
import { CHART_HEIGHT } from "@/components/weeklyPointsChartHeight";

/**
 * Lazy entry points for the recharts-backed weekly points charts. The charts
 * only mount after their data has loaded, yet a static import shipped the whole
 * recharts chunk (~110 KB gzip) with the player profile and player compare
 * routes before they could paint anything. The loading placeholder reserves the
 * chart's exact height (CHART_HEIGHT), so the swap does not shift layout.
 */
const chartSkeleton = () => <SkeletonBlock height={CHART_HEIGHT} />;

export const WeeklyPointsPanel = dynamic(
  () => import("@/components/WeeklyPointsChart").then((m) => m.WeeklyPointsPanel),
  { ssr: false, loading: chartSkeleton },
);

export const WeeklyPointsChart = dynamic(
  () => import("@/components/WeeklyPointsChart").then((m) => m.WeeklyPointsChart),
  { ssr: false, loading: chartSkeleton },
);

/** Start fetching the chart chunk now (in parallel with the page's own data fetch). */
export function usePreloadWeeklyPointsChart(): void {
  useEffect(() => {
    void import("@/components/WeeklyPointsChart");
  }, []);
}
