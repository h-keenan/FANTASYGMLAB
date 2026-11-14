"use client";

import Image from "next/image";
import Link from "next/link";
import { useParams, usePathname } from "next/navigation";
import type { ReactNode } from "react";

import { SHELL_PAGE_INFO_SLOT_ID } from "@/components/PageTitle";
import { PAGE_TITLE_BY_SEGMENT } from "@/lib/navDestinations";
import { shellLeagueContext, shellParent } from "@/lib/shellNav";
import { useSearchParams } from "@/lib/useSearchParams";
import { useShellNav } from "@/lib/useShellNav";
import { UNNAMED_LEAGUE } from "@/lib/leagueName";

/**
 * The one standard phone page header (Phase B): back (named for the parent
 * page, e.g. "< Players"), the page title, the league chip, search and the
 * alerts bell (both from Header's own pieces, passed in so the notification
 * dropdown stays one component). Phones only; Header hides its own row below
 * 768px when this renders, so there is exactly one header.
 */
export function ShellHeader({ leagueControls, actions }: { leagueControls: ReactNode; actions: ReactNode }) {
  const { barVisible } = useShellNav();
  const pathname = usePathname();
  const params = useParams<{ leagueId?: string }>();
  const searchParams = useSearchParams();
  if (!barVisible) return null;
  const { leagueId, leagueName } = shellLeagueContext(params?.leagueId ? decodeURIComponent(params.leagueId) : null, searchParams, UNNAMED_LEAGUE);
  const segment = (pathname || "").split("/").filter(Boolean)[0] ?? "";
  const title = segment ? PAGE_TITLE_BY_SEGMENT[segment] ?? "" : "Home";
  const parent = shellParent(pathname, { leagueId, leagueName });
  return (
    <header className="shell-header md:hidden" data-testid="shell-header">
      {parent ? (
        <Link href={parent.href} className="shell-header-back" aria-label={`Back to ${parent.label}`}>
          <svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="m15 18-6-6 6-6" />
          </svg>
          <span className="truncate text-xs font-bold">{parent.label}</span>
        </Link>
      ) : (
        <Link href="/" aria-label="FantasyDesk home" className="shell-header-back">
          <Image src="/brand-mark.png" alt="" width={26} height={26} className="brand-mark-icon" style={{ objectFit: "contain" }} />
        </Link>
      )}
      <h1 className="min-w-0 shrink truncate text-sm font-extrabold" data-testid="shell-title">{title}</h1>
      <span id={SHELL_PAGE_INFO_SLOT_ID} className="inline-flex" />
      <div className="flex min-w-0 flex-1 justify-end">{leagueControls}</div>
      <div className="flex shrink-0 items-center">{actions}</div>
    </header>
  );
}
