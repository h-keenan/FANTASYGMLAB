"use client";

import { useParams, useRouter } from "next/navigation";
import { useEffect } from "react";

import { useSearchParams } from "@/lib/useSearchParams";
import { useAuth } from "@/context/AuthContext";
import { CommissionerContent } from "@/components/CommissionerContent";
import { LoadingScreen } from "@/components/LoadingScreen";

export default function CommissionerPage() {
  const params = useParams<{ leagueId: string }>();
  const searchParams = useSearchParams();
  const router = useRouter();
  const { session, loading: authLoading } = useAuth();

  const leagueId = decodeURIComponent(params.leagueId);
  const leagueName = searchParams.get("name") || leagueId;

  useEffect(() => {
    if (!authLoading && !session) router.replace("/");
  }, [authLoading, session, router]);

  if (authLoading || !session) return <LoadingScreen status="Loading League integrity…" />;
  return <CommissionerContent leagueId={leagueId} leagueName={leagueName} />;
}
