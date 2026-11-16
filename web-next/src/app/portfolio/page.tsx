"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";

import { LoadingScreen } from "@/components/LoadingScreen";
import { PORTFOLIO_REDIRECT_TARGET } from "@/lib/retiredRoutes";

// Retired route (2026-11-16 nav consolidation: Home + Portfolio became one): forwards to Home's standing section.
export default function RetiredPortfolioPage() {
  const router = useRouter();
  useEffect(() => {
    router.replace(PORTFOLIO_REDIRECT_TARGET);
  }, [router]);
  return <LoadingScreen label="Your leagues" layout="dashboard" />;
}
