import { NextResponse } from "next/server";

import { loadTradeBoard } from "@/lib/seo/tradeBoardServer";

// Compact, anonymous, league-agnostic value payload for the public Trade
// Analyzer's player search: 1QB/Superflex x with/without tight-end premium,
// merged into one list (see lib/seo/tradeAnalyzer.ts mergeBoards). Read-only;
// each upstream fetch is itself cached for a day (SEO_REVALIDATE_SECONDS).
export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const body = await loadTradeBoard();
    return NextResponse.json(body, {
      headers: { "Cache-Control": "public, max-age=300, s-maxage=3600, stale-while-revalidate=86400" },
    });
  } catch {
    return NextResponse.json({ error: "Player values are not available right now." }, { status: 503 });
  }
}
