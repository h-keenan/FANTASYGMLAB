import type { CSSProperties, ReactNode } from "react";

import { SimCrest } from "@/components/SimCrest";
import { SIM_TEAM_SIZES, simTeamNameFit, type SimTeamSize } from "@/lib/simTeamIdentity";

/**
 * The generated team logo at a slot from the size table (lib/simTeamIdentity.ts: inline 16 / chip 20 / row 28 / card 44 / hero 56 /
 * sheet 72). The ONLY place a sim component may mount SimCrest (guarded by lib/simTeamIdentityRule.test.ts); use it when the name is
 * printed by the surrounding layout. `label` makes the logo its own accessible image.
 */
export function SimTeamLogo({ name, size = "row", label = false }: { name: string; size?: SimTeamSize; label?: boolean }) {
  return <SimCrest name={name} size={SIM_TEAM_SIZES[size]} label={label} />;
}

/**
 * THE way a Fantasy Sim team is shown: logo + name. The name is never ellipsized and never cut mid-word: it walks the fit ladder
 * (full name, wrapped to two balanced lines, one font step smaller; lib/simTeamIdentity.ts). `stacked` puts the logo above a
 * centered name (matchup / recap sides). `hideName` renders the logo alone (the name is printed beside it by the layout).
 */
export function SimTeamIdentity({
  name,
  size = "row",
  stacked = false,
  isYou = false,
  suffix,
  bold = true,
  hideName = false,
  className = "",
  nameClassName = "",
  nameStyle,
}: {
  name: string;
  size?: SimTeamSize;
  stacked?: boolean;
  isYou?: boolean;
  suffix?: ReactNode;
  bold?: boolean;
  hideName?: boolean;
  className?: string;
  nameClassName?: string;
  nameStyle?: CSSProperties;
}) {
  const fit = simTeamNameFit(name, stacked);
  const layout = stacked ? "flex-col justify-center text-center gap-1" : "items-center gap-2";
  return (
    <span className={`inline-flex min-w-0 ${layout} ${className}`} data-testid="sim-team-identity">
      <SimTeamLogo name={name} size={size} />
      {hideName ? null : (
        <span
          className={`min-w-0 break-words text-sm ${bold ? "font-bold" : "font-medium"} ${nameClassName}`}
          data-fit-stage={fit.stage}
          style={{ textWrap: fit.wrap ? "balance" : undefined, whiteSpace: fit.wrap ? "normal" : "nowrap", fontSize: fit.scale === 1 ? undefined : `${fit.scale}em`, overflowWrap: "break-word", ...nameStyle }}
        >
          {name}
          {isYou ? " (you)" : ""}
        </span>
      )}
      {suffix}
    </span>
  );
}
