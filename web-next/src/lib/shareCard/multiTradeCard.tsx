/**
 * Multi-team trade share card: the picture a manager sends to the other
 * managers to pitch a 3 to 6 team deal. Leads with a one-line "biggest gain"
 * verdict, draws who sends what to whom (a table for 3 teams, per-card
 * "from" notes for 4+), then one self-explanatory card per team: what it
 * gets, what it sends, the need it fills, and its true value change (green
 * gain, red loss, neutral even; nothing hidden). No "most hurt" / "loses"
 * words. Cards size to their content; density steps down with team count so
 * 4 to 6 teams scale down instead of overflowing the canvas.
 *
 * Data comes from lib/multiTeamTrade.ts buildShareModel (the same model the
 * mobile card draws). Satori only, like tradeCard.tsx; no network, no quota.
 */

import { BRAND_DOMAIN, BRAND_NAME } from "@/lib/brand";
import type { ShareEdge, ShareModel, ShareTeam, ShareValueTone } from "@/lib/multiTeamTrade";

import { ShareAvatar, ShareFrame, ShareQr, eyebrowStyle, glassStyle, initials, type ShareBrandAssets } from "./frame";
import { SHARE_TOKEN_HEX as T, shareRadius, withAlpha } from "./tokens";

const MAX_EDGE_ROWS = 4;

interface Density {
  avatar: number;
  name: number;
  line: number;
  detail: number;
  value: number;
  pad: string;
  gap: number;
  assets: number;
  needs: number;
}

/** One density step per team count, chosen so the stack fits 1350px. */
function densityFor(teamCount: number): Density {
  if (teamCount <= 3) return { avatar: 50, name: 28, line: 22, detail: 18, value: 36, pad: "14px 24px", gap: 4, assets: 3, needs: 1 };
  if (teamCount === 4) return { avatar: 46, name: 26, line: 21, detail: 17, value: 32, pad: "12px 22px", gap: 3, assets: 2, needs: 1 };
  return { avatar: 38, name: 22, line: 18, detail: 16, value: 28, pad: "10px 18px", gap: 2, assets: 2, needs: 0 };
}

const TONE_COLOR: Record<ShareValueTone, string> = {
  gain: T["--color-success"],
  loss: T["--color-danger"],
  even: T["--color-text-primary"],
};

const oneLine = { display: "block", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" } as const;

function listLabels(labels: string[], limit: number): string {
  return labels.slice(0, limit).join(", ") + (labels.length > limit ? ` +${labels.length - limit}` : "");
}

function EdgeTeam({ name, avatar }: { name: string; avatar: string | null }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, width: 292, flexShrink: 0, minWidth: 0 }}>
      <div style={{ display: "flex", flexShrink: 0 }}>
        <ShareAvatar src={avatar} size={44} fallbackText={initials(name)} />
      </div>
      <div style={{ ...oneLine, flexGrow: 1, flexShrink: 1, minWidth: 0, fontSize: 22, fontWeight: 800, lineHeight: 1.15 }}>{name}</div>
    </div>
  );
}

function EdgeRow({ edge }: { edge: ShareEdge }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, minHeight: 56 }}>
      <EdgeTeam name={edge.fromName} avatar={edge.fromAvatarUrl} />
      <svg width="40" height="24" viewBox="0 0 64 28" fill="none" stroke={T["--color-accent"]} strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
        <path d="M4 14h52M44 4l12 10-12 10" />
      </svg>
      <EdgeTeam name={edge.toName} avatar={edge.toAvatarUrl} />
      <div style={{ display: "block", flexGrow: 1, flexShrink: 1, minWidth: 0, fontSize: 20, fontWeight: 600, color: T["--color-text-secondary"], lineHeight: 1.15, lineClamp: 2 }}>{listLabels(edge.labels, 2)}</div>
    </div>
  );
}

function FlowSection({ edges }: { edges: ShareEdge[] }) {
  const shown = edges.slice(0, MAX_EDGE_ROWS);
  return (
    <div style={{ ...glassStyle(), flexDirection: "column", padding: "18px 28px", gap: 4, flexShrink: 0 }}>
      <div style={{ ...eyebrowStyle(T["--color-accent"], 22), letterSpacing: "0.18em" }}>Who sends what</div>
      {shown.map((edge) => (
        <EdgeRow key={`${edge.fromRosterId}>${edge.toRosterId}`} edge={edge} />
      ))}
      {edges.length > shown.length ? <div style={{ display: "flex", fontSize: 20, fontWeight: 700, color: T["--color-text-muted"] }}>{`+${edges.length - shown.length} more`}</div> : null}
    </div>
  );
}

function TeamCard({ team, density, showFrom }: { team: ShareTeam; density: Density; showFrom: boolean }) {
  const gets = listLabels(
    team.gets.map((a) => (showFrom && a.from_team_name ? `${a.label} (from ${a.from_team_name})` : a.label)),
    density.assets,
  );
  const sends = listLabels(
    team.sends.map((a) => a.label),
    density.assets,
  );
  const needs = team.needs.slice(0, density.needs);
  return (
    <div style={{ ...glassStyle(shareRadius("--radius-md")), flexDirection: "column", flexShrink: 0, gap: density.gap + 4, padding: density.pad, border: `1.5px solid ${withAlpha(T["--color-accent"], 0.3)}` }}>
      <div style={{ display: "flex", alignItems: "center", gap: 18 }}>
        <div style={{ display: "flex", flexShrink: 0 }}>
          <ShareAvatar src={team.avatarUrl} size={density.avatar} fallbackText={initials(team.name)} />
        </div>
        <div style={{ ...oneLine, flexGrow: 1, flexShrink: 1, minWidth: 0, fontSize: density.name, fontWeight: 900, lineHeight: 1.15 }}>{team.name}</div>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", flexShrink: 0 }}>
          <div style={{ ...eyebrowStyle(T["--color-text-muted"], 14), letterSpacing: "0.14em" }}>Value change</div>
          <div style={{ display: "flex", fontSize: density.value, fontWeight: 900, lineHeight: 1.05, color: TONE_COLOR[team.valueTone] }}>{team.valueChangeText}</div>
        </div>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: density.gap }}>
        <div style={{ display: "block", fontSize: density.line, fontWeight: 700, lineHeight: 1.2, color: T["--color-accent"], lineClamp: 2 }}>{`Gets ${gets || "nothing"}`}</div>
        <div style={{ display: "block", fontSize: density.line, fontWeight: 700, lineHeight: 1.2, color: T["--color-text-secondary"], lineClamp: 2 }}>{`Sends ${sends || "nothing"}`}</div>
        {needs.map((line) => (
          <div key={line} style={{ ...oneLine, fontSize: density.detail, fontWeight: 600, lineHeight: 1.2, color: T["--color-text-muted"] }}>{`• ${line}`}</div>
        ))}
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
  const density = densityFor(model.teams.length);
  const verdictTeam = model.teams.find((t) => t.rosterId === model.verdict.topRosterId);
  return (
    <ShareFrame brand={brand} kind="Trade proposal" width={width} height={height} footer={false}>
      <div style={{ display: "flex", flexDirection: "column", gap: 8, flexShrink: 0 }}>
        <div style={{ display: "block", fontSize: 48, fontWeight: 900, lineHeight: 1.05, letterSpacing: "-0.02em" }}>{`${model.teams.length}-team trade`}</div>
        <div style={{ ...oneLine, fontSize: 26, fontWeight: 600, color: T["--color-text-secondary"] }}>
          {`Here is what every team gets and sends${leagueName ? ` in ${leagueName}` : ""}`}
        </div>
        <div style={{ ...oneLine, fontSize: 26, fontWeight: 800, color: verdictTeam ? T["--color-success"] : T["--color-text-muted"] }}>{model.verdict.text}</div>
      </div>
      {flow ? <FlowSection edges={model.edges} /> : null}
      <div style={{ display: "flex", flexDirection: "column", gap: 12, flexShrink: 0 }}>
        {model.teams.map((team) => (
          <TeamCard key={team.rosterId} team={team} density={density} showFrom={!flow} />
        ))}
      </div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0 }}>
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
          <div style={{ display: "flex", fontSize: 26, fontWeight: 800 }}>{BRAND_DOMAIN}</div>
          <div style={{ display: "flex", fontSize: 18, fontWeight: 500, color: T["--color-text-muted"] }}>{`Analyze your own deal in ${BRAND_NAME}`}</div>
        </div>
        <ShareQr brand={brand} size={80} />
      </div>
    </ShareFrame>
  );
}
