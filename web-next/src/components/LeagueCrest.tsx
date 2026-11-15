"use client";

import { useState } from "react";

import { leagueCrestColors, leagueInitials } from "@/lib/leagueCrest";

/**
 * The league's picture: its avatar when a caller has one, else the generated crest (a stable colour per league id with the league's
 * initials, lib/leagueCrest.ts). Same on web and app (mobile/src/components/LeagueCrest.tsx), so a league is recognisable everywhere.
 */
export function LeagueCrest({ leagueId, name, avatarUrl, size = 32 }: { leagueId?: string | null; name?: string | null; avatarUrl?: string | null; size?: number }) {
  const [failed, setFailed] = useState(false);
  const dim = { width: size, height: size, borderRadius: "50%" } as const;
  if (avatarUrl && !failed) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img src={avatarUrl} alt="" loading="lazy" decoding="async" style={{ ...dim, objectFit: "cover", border: "2px solid var(--color-border)" }} className="shrink-0" onError={() => setFailed(true)} />
    );
  }
  const c = leagueCrestColors(leagueId || name);
  return (
    <span aria-hidden="true" data-testid="league-crest" className="inline-flex shrink-0 items-center justify-center font-extrabold" style={{ ...dim, background: c.fill, color: c.ink, border: `2px solid ${c.ring}`, fontSize: Math.max(9, Math.round(size * 0.36)) }}>
      {leagueInitials(name)}
    </span>
  );
}
