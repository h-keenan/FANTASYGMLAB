/**
 * Multi-team trade share card: the picture a manager sends to the other
 * managers to pitch a 3 to 6 team deal. Persuasion framed, not a scoreboard:
 * it leads with what each team GETS and which needs that fills, draws who
 * sends what to whom (a flow for 3 teams, a list for 4+), and uses no
 * "most hurt" / "loses" words and no red verdicts. Nothing is hidden: every
 * team's true value change is printed as a plain, neutral number, and a team
 * that gives up value says what it gets back.
 *
 * Data comes from lib/multiTeamTrade.ts buildShareModel (the same model the
 * mobile card draws). Satori only, like tradeCard.tsx; no network, no quota.
 */

import { BRAND_DOMAIN, BRAND_NAME } from "@/lib/brand";
import type { ShareEdge, ShareModel, ShareTeam } from "@/lib/multiTeamTrade";

import { ShareAvatar, ShareFrame, ShareQr, eyebrowStyle, glassStyle, initials, type ShareBrandAssets } from "./frame";
import { SHARE_TOKEN_HEX as T, shareRadius, withAlpha } from "./tokens";

const MAX_EDGE_ROWS = 4;

function EdgeRow({ edge }: { edge: ShareEdge }) {
  const labels = edge.labels.slice(0, 3).join(", ") + (edge.labels.length > 3 ? ` +${edge.labels.length - 3}` : "");
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 16, minHeight: 76 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 12, width: 230, flexShrink: 0 }}>
        <ShareAvatar src={null} size={48} fallbackText={initials(edge.fromName)} />
        <div style={{ display: "block", fontSize: 24, fontWeight: 800, lineHeight: 1.1, lineClamp: 2 }}>{edge.fromName}</div>
      </div>
      <svg width="64" height="28" viewBox="0 0 64 28" fill="none" stroke={T["--color-accent"]} strokeWidth="4" strokeLinecap="round" strokeLinejoin="round">
        <path d="M4 14h52M44 4l12 10-12 10" />
      </svg>
      <div style={{ display: "flex", alignItems: "center", gap: 12, width: 230, flexShrink: 0 }}>
        <ShareAvatar src={null} size={48} fallbackText={initials(edge.toName)} />
        <div style={{ display: "block", fontSize: 24, fontWeight: 800, lineHeight: 1.1, lineClamp: 2 }}>{edge.toName}</div>
      </div>
      <div style={{ display: "block", flexGrow: 1, flexShrink: 1, minWidth: 0, fontSize: 22, fontWeight: 600, color: T["--color-text-secondary"], lineHeight: 1.15, lineClamp: 2 }}>{labels}</div>
    </div>
  );
}

function FlowSection({ edges }: { edges: ShareEdge[] }) {
  const shown = edges.slice(0, MAX_EDGE_ROWS);
  return (
    <div style={{ ...glassStyle(), flexDirection: "column", padding: "20px 28px", gap: 6, flexShrink: 0 }}>
      <div style={{ ...eyebrowStyle(T["--color-accent"], 22), letterSpacing: "0.18em" }}>Who sends what</div>
      {shown.map((edge) => (
        <EdgeRow key={`${edge.fromRosterId}>${edge.toRosterId}`} edge={edge} />
      ))}
      {edges.length > shown.length ? <div style={{ display: "flex", fontSize: 20, fontWeight: 700, color: T["--color-text-muted"] }}>{`+${edges.length - shown.length} more`}</div> : null}
    </div>
  );
}

function TeamCard({ team, compact, showFrom }: { team: ShareTeam; compact: boolean; showFrom: boolean }) {
  const limit = compact ? 3 : 4;
  const gets = team.gets
    .slice(0, limit)
    .map((a) => (showFrom && a.from_team_name ? `${a.label} (from ${a.from_team_name})` : a.label))
    .join(", ");
  const more = team.gets.length - limit;
  const detail = [...team.needs, ...(team.getsBack ? [team.getsBack] : [])].slice(0, 2);
  return (
    <div style={{ ...glassStyle(shareRadius("--radius-md")), flexGrow: 1, flexBasis: 0, minWidth: 0, alignItems: "center", gap: 20, padding: compact ? "14px 22px" : "20px 28px", border: `1.5px solid ${withAlpha(T["--color-accent"], 0.3)}` }}>
      <ShareAvatar src={null} size={compact ? 60 : 76} fallbackText={initials(team.name)} />
      <div style={{ display: "flex", flexDirection: "column", flexGrow: 1, flexShrink: 1, minWidth: 0, gap: compact ? 4 : 8 }}>
        <div style={{ display: "block", fontSize: compact ? 26 : 32, fontWeight: 900, lineHeight: 1.1, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{team.name}</div>
        <div style={{ display: "block", fontSize: compact ? 21 : 25, fontWeight: 700, lineHeight: 1.2, color: T["--color-accent"], lineClamp: 2 }}>
          {`Gets ${gets || "nothing"}${more > 0 ? ` +${more} more` : ""}`}
        </div>
        {detail.map((line) => (
          <div key={line} style={{ display: "block", fontSize: compact ? 18 : 21, fontWeight: 600, lineHeight: 1.2, color: T["--color-text-secondary"], whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{`• ${line}`}</div>
        ))}
      </div>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", flexShrink: 0, gap: 2 }}>
        <div style={{ ...eyebrowStyle(T["--color-text-muted"], 15), letterSpacing: "0.14em" }}>Value change</div>
        <div style={{ display: "flex", fontSize: compact ? 34 : 44, fontWeight: 900, lineHeight: 1.05, color: T["--color-text-primary"] }}>{team.valueChangeText}</div>
      </div>
    </div>
  );
}

export function MultiTradeShareCard({
  model,
  leagueName,
  brand,
  width,
  height,
}: {
  model: ShareModel;
  leagueName?: string | null;
  brand: ShareBrandAssets;
  width: number;
  height: number;
}) {
  const flow = model.layout === "flow";
  const compact = !flow || model.teams.length > 3;
  return (
    <ShareFrame brand={brand} kind="Trade proposal" width={width} height={height} footer={false}>
      <div style={{ display: "flex", flexDirection: "column", gap: 8, flexShrink: 0 }}>
        <div style={{ display: "block", fontSize: 56, fontWeight: 900, lineHeight: 1.05, letterSpacing: "-0.02em" }}>{`${model.teams.length}-team trade`}</div>
        <div style={{ display: "block", fontSize: 26, fontWeight: 600, color: T["--color-text-secondary"] }}>
          {`Here is what every team gets${leagueName ? ` in ${leagueName}` : ""}`}
        </div>
      </div>
      {flow ? <FlowSection edges={model.edges} /> : null}
      <div style={{ display: "flex", flexDirection: "column", flexGrow: 1, gap: 16 }}>
        {model.teams.map((team) => (
          <TeamCard key={team.rosterId} team={team} compact={compact} showFrom={!flow} />
        ))}
      </div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <div style={{ display: "flex", fontSize: 26, fontWeight: 800 }}>{BRAND_DOMAIN}</div>
          <div style={{ display: "flex", fontSize: 18, fontWeight: 500, color: T["--color-text-muted"] }}>{`Analyze your own deal in ${BRAND_NAME}`}</div>
        </div>
        <ShareQr brand={brand} size={92} />
      </div>
    </ShareFrame>
  );
}
