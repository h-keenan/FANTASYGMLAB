"use client";

import { useEffect } from "react";

/**
 * The weekly points charts used to be recharts behind next/dynamic (~110 KB gzip). They are now the shared
 * dependency-free TrendChart, so there is nothing to lazy-load: these re-exports keep the import sites stable.
 */
export { WeeklyPointsChart, WeeklyPointsPanel } from "@/components/WeeklyPointsChart";

/** No-op now (the chart ships in the page bundle); kept so call sites do not change. */
export function usePreloadWeeklyPointsChart(): void {
  useEffect(() => {}, []);
}
