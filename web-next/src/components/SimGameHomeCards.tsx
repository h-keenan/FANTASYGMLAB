"use client";

import { AccentCard } from "@/components/AccentCard";
import { Button } from "@/components/Button";
import { PositionBadge } from "@/components/PositionBadge";
import { SimGlyph } from "@/components/SimGlyph";
import {
  SimMiniPlayer,
  SimPlayerChip,
  SimSectionTitle,
  SimTeamLink,
  SimToneBadge,
  SimTrend,
  simToneColor,
  type SimCtx,
} from "@/components/SimGameParts";
import { ToneBadge } from "@/components/ToneBadge";
import {
  simFmtPts,
  simFmtRecord,
  simMarginLine,
  simPlayoffStatusLabel,
  simStandingsWindow,
  type SimByeAlert,
  type SimGamePlayer,
  type SimHomeResponse,
  type SimWaiverSuggestion,
} from "@/lib/simGame";
import type { SimTab } from "@/lib/simGameFlow";

type OnTab = (tab: SimTab) => void;

function LinkButton({ children, onClick }: { children: React.ReactNode; onClick: () => void }) {
  return (
    <button type="button" className="tap-link self-start text-xs font-bold" style={{ color: "var(--color-accent)", minHeight: "var(--touch-target-min)" }} onClick={onClick}>
      {children}
    </button>
  );
}

/** Upcoming byes that leave a starter hole, with the bench cover or free agents to claim. */
export function SimByeCard({ ctx, alerts, onTab, onClaim }: { ctx: SimCtx; alerts: SimByeAlert[]; onTab: OnTab; onClaim: (p: SimGamePlayer) => void }) {
  if (alerts.length === 0) return null;
  const uncovered = alerts.filter((a) => !a.covered).length;
  return (
    <AccentCard accent={uncovered ? "var(--color-warning)" : "var(--color-success)"} as="section">
      <SimSectionTitle glyph="bye" tone={uncovered ? "warning" : "success"} note="Starters whose NFL team is off in the next few weeks.">Bye-week cover</SimSectionTitle>
      <ul className="flex flex-col gap-3" aria-label="Bye week alerts">
        {alerts.map((a) => (
          <li key={`${a.week}-${a.player.id}`} className="flex flex-col gap-2" data-testid="bye-alert">
            <div className="flex items-center gap-2">
              <ToneBadge label={a.weeks_away === 0 ? "This week" : `Week ${a.week}`} color={a.weeks_away === 0 ? "var(--color-danger)" : "var(--color-warning)"} size="xs" />
              <PositionBadge position={a.player.pos} label={a.pos_label} />
              <ToneBadge label={a.covered ? "Covered" : "Needs cover"} color={a.covered ? "var(--color-success)" : "var(--color-danger)"} size="xs" />
            </div>
            <SimPlayerChip player={{ ...a.player, status: "bye" }} size={32} hidePosition />
            <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>{a.message}</p>
            {a.covered && a.covered_by ? (
              <div className="flex items-center gap-2 text-xs" style={{ color: "var(--color-success)" }}>
                <SimGlyph name="check" size={14} />
                <SimMiniPlayer player={a.covered_by} onOpen={ctx.openPlayer} />
              </div>
            ) : a.replacements.length > 0 ? (
              <ul className="flex flex-col gap-1" aria-label="Free agents who could fill in">
                {a.replacements.map((r) => (
                  <li key={r.id} className="flex items-center justify-between gap-2">
                    <SimMiniPlayer player={r} onOpen={ctx.openPlayer} />
                    <span className="flex shrink-0 items-center gap-2">
                      <span className="text-xs font-bold tabular-nums">{simFmtPts(r.projection)} proj</span>
                      <Button size="sm" onClick={() => onClaim(r)} aria-label={`Claim ${r.name}`}>Claim</Button>
                    </span>
                  </li>
                ))}
              </ul>
            ) : null}
          </li>
        ))}
      </ul>
      {uncovered ? <LinkButton onClick={() => onTab("players")}>Open the waiver wire</LinkButton> : null}
    </AccentCard>
  );
}

/** Free agents who would improve your lineup, each with the factors behind the suggestion. */
export function SimWaiverCard({ ctx, suggestions, onClaim, onTab }: { ctx: SimCtx; suggestions: SimWaiverSuggestion[]; onClaim: (p: SimGamePlayer) => void; onTab: OnTab }) {
  return (
    <AccentCard accent="var(--color-success)" as="section">
      <SimSectionTitle glyph="waiver" tone="success" note="Free agents that fix a hole or upgrade a starter.">Waiver targets</SimSectionTitle>
      {suggestions.length === 0 ? (
        <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>Nothing on the wire beats your roster right now. Check back after the next games.</p>
      ) : (
        <ul className="flex flex-col gap-3" aria-label="Waiver suggestions">
          {suggestions.map((s) => (
            <li key={s.player.id} className="flex flex-col gap-1.5" data-testid="waiver-suggestion">
              <div className="flex items-center justify-between gap-2">
                <button type="button" className="min-w-0 flex-1 text-left" onClick={() => ctx.openPlayer(s.player)} aria-label={`${s.player.name}, ${s.player.pos}. Open player details`}>
                  <SimPlayerChip player={s.player} size={36} />
                </button>
                <span className="flex shrink-0 flex-col items-end leading-tight">
                  <SimTrend delta={Math.max(s.gain_now, s.gain_ros)} />
                  <span className="text-[0.6875rem]" style={{ color: "var(--color-text-muted)" }}>{s.gain_now >= s.gain_ros ? "this week" : "per week"}</span>
                </span>
                <Button size="sm" onClick={() => onClaim(s.player)} aria-label={`Claim ${s.player.name}`}>Claim</Button>
              </div>
              <ul className="flex flex-col gap-0.5 pl-1">
                {s.reasons.map((r) => (
                  <li key={r} className="flex items-start gap-1.5 text-xs" style={{ color: "var(--color-text-secondary)" }}>
                    <span aria-hidden="true" style={{ color: "var(--color-success)" }}>+</span>
                    <span className="min-w-0">{r}</span>
                  </li>
                ))}
                {s.drop ? (
                  <li className="flex items-start gap-1.5 text-xs" style={{ color: "var(--color-text-muted)" }}>
                    <span aria-hidden="true" style={{ color: "var(--color-danger)" }}>-</span>
                    <span className="min-w-0">Your roster is full: drop {s.drop.name} ({s.drop.pos})</span>
                  </li>
                ) : null}
              </ul>
            </li>
          ))}
        </ul>
      )}
      <LinkButton onClick={() => onTab("players")}>Browse every free agent</LinkButton>
    </AccentCard>
  );
}

/** Trade offers waiting on you, with the badge count. */
export function SimInboxCard({ ctx, inbox, onTab }: { ctx: SimCtx; inbox: SimHomeResponse["inbox"]; onTab: OnTab }) {
  if (!inbox || !inbox.open) return null;
  const { count, items } = inbox;
  return (
    <AccentCard accent={count ? "var(--color-accent)" : "var(--color-border-strong)"} as="section">
      <SimSectionTitle glyph="trade" tone={count ? "accent" : "muted"} action={count ? <ToneBadge label={`${count} new`} color="var(--color-accent)" /> : undefined}>Trade inbox</SimSectionTitle>
      {count === 0 ? (
        <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>No offers waiting. AI managers send new ones most weeks.</p>
      ) : (
        <ul className="flex flex-col gap-3" aria-label="Trade offers">
          {items.map((o) => (
            <li key={o.id} className="flex flex-col gap-1.5">
              <div className="flex items-center justify-between gap-2">
                <SimTeamLink teamId={o.from.team_id} name={o.from.name} />
                <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>expires wk {o.expires_week}</span>
              </div>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div className="flex flex-col gap-1">
                  <span className="font-extrabold uppercase" style={{ color: "var(--color-danger)", letterSpacing: "var(--letter-spacing-badge)" }}>You give</span>
                  {o.you_give.map((p) => <SimMiniPlayer key={p.id} player={p} onOpen={ctx.openPlayer} size={24} />)}
                </div>
                <div className="flex flex-col gap-1">
                  <span className="font-extrabold uppercase" style={{ color: "var(--color-success)", letterSpacing: "var(--letter-spacing-badge)" }}>You get</span>
                  {o.you_get.map((p) => <SimMiniPlayer key={p.id} player={p} onOpen={ctx.openPlayer} size={24} />)}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
      <Button size="sm" variant={count ? "primary" : "secondary"} onClick={() => onTab("trades")}>{count ? "Review offers" : "Open Trades"}</Button>
    </AccentCard>
  );
}

/** Injured players on your roster, starters first. */
export function SimInjuriesCard({ ctx, injuries }: { ctx: SimCtx; injuries: SimHomeResponse["injuries"] }) {
  const list = injuries ?? [];
  return (
    <AccentCard accent={list.some((i) => i.starting) ? "var(--color-danger)" : "var(--color-border-strong)"} as="section">
      <SimSectionTitle glyph="injury" tone={list.length ? "danger" : "muted"}>Injury report</SimSectionTitle>
      {list.length === 0 ? (
        <p className="flex items-center gap-2 text-sm" style={{ color: "var(--color-success)" }}><SimGlyph name="check" size={14} />Everyone on your roster is healthy.</p>
      ) : (
        <ul className="flex flex-col gap-2" aria-label="Injuries on your roster">
          {list.map((i) => (
            <li key={i.player.id} className="flex items-center justify-between gap-2" data-testid="home-injury">
              <button type="button" className="min-w-0 flex-1 text-left" onClick={() => ctx.openPlayer(i.player)} aria-label={`${i.player.name}, ${i.player.pos}. Open player details`}>
                <SimPlayerChip player={i.player} size={36} />
              </button>
              <span className="flex shrink-0 flex-col items-end gap-1">
                <SimToneBadge label={`Out ${i.out_weeks} wk`} tone="danger" />
                <span className="text-[0.6875rem]" style={{ color: i.starting ? "var(--color-warning)" : "var(--color-text-muted)" }}>{i.starting ? "In your lineup" : i.note}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
    </AccentCard>
  );
}

/** Where you sit and the playoff cut line. */
export function SimStandingsCard({ standings, onTab }: { standings: SimHomeResponse["standings"]; onTab: OnTab }) {
  if (!standings) return null;
  const rows = simStandingsWindow(standings.rows, 6);
  const margin = simMarginLine(standings);
  const mTone = standings.margin == null ? "var(--color-text-secondary)" : standings.margin >= 0 ? "var(--color-success)" : "var(--color-danger)";
  return (
    <AccentCard accent={standings.in_playoffs ? "var(--color-success)" : "var(--color-warning)"} as="section">
      <SimSectionTitle glyph="standings" tone={standings.in_playoffs ? "success" : "warning"} action={<ToneBadge label={standings.in_playoffs ? "In the playoffs" : "Outside"} color={standings.in_playoffs ? "var(--color-success)" : "var(--color-warning)"} />}>
        Playoff picture
      </SimSectionTitle>
      {margin ? <p className="text-xs font-bold" style={{ color: mTone }}>{margin}</p> : null}
      <ol className="flex flex-col" aria-label="Standings snapshot">
        {rows.map((r) => {
          const cut = r.rank === standings.playoff_spots;
          const label = simPlayoffStatusLabel(r.playoff_status);
          return (
            <li
              key={r.team_id}
              className="grid grid-cols-[1.25rem_1fr_auto_auto] items-center gap-2 px-1"
              style={{
                borderBottom: cut ? "2px dashed var(--color-success)" : "var(--border-width-default) solid var(--color-border)",
                background: r.is_you ? "var(--color-accent-soft)" : undefined,
              }}
            >
              <span className="text-xs font-extrabold tabular-nums" style={{ color: r.rank <= standings.playoff_spots ? "var(--color-success)" : "var(--color-text-muted)" }}>{r.rank}</span>
              <SimTeamLink teamId={r.team_id} name={r.name} isYou={r.is_you} size={22} bold={r.is_you} />
              <span className="text-xs tabular-nums" style={{ color: r.streak?.startsWith("W") ? "var(--color-success)" : r.streak?.startsWith("L") ? "var(--color-danger)" : "var(--color-text-muted)" }}>{r.streak ?? ""}</span>
              <span className="text-sm font-bold tabular-nums" title={label || undefined}>{simFmtRecord(r)}</span>
            </li>
          );
        })}
      </ol>
      <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>Dashed line: top {standings.playoff_spots} make the playoffs.</p>
      <LinkButton onClick={() => onTab("league")}>Full standings</LinkButton>
    </AccentCard>
  );
}

/** Your hottest and coldest players, and who is hot on the wire. */
export function SimHotColdCard({ ctx, hotCold, onClaim }: { ctx: SimCtx; hotCold: SimHomeResponse["hot_cold"]; onClaim: (p: SimGamePlayer) => void }) {
  if (!hotCold) return null;
  const { hot, cold, wire } = hotCold;
  if (hot.length + cold.length + wire.length === 0) return null;
  const rows = (
    list: typeof hot,
    glyph: "hot" | "cold" | "waiver",
    title: string,
    tone: "danger" | "accent" | "success",
    claim = false,
  ) =>
    list.length === 0 ? null : (
      <div className="flex flex-col gap-1.5" key={title}>
        <SimSectionTitle glyph={glyph} tone={tone}>{title}</SimSectionTitle>
        <ul className="flex flex-col gap-2">
          {list.map((t) => (
            <li key={t.player.id} className="flex items-center justify-between gap-2" data-testid="trend-row">
              <SimMiniPlayer player={t.player} onOpen={ctx.openPlayer} size={30} />
              <span className="flex shrink-0 items-center gap-2 text-xs">
                <span className="tabular-nums font-bold">{simFmtPts(t.last_week)} pts</span>
                <SimTrend delta={t.delta} suffix=" vs proj" />
                {claim ? <Button size="sm" variant="secondary" onClick={() => onClaim(t.player)} aria-label={`Claim ${t.player.name}`}>Claim</Button> : null}
              </span>
            </li>
          ))}
        </ul>
      </div>
    );
  return (
    <AccentCard accent="var(--color-premium)" as="section">
      <SimSectionTitle glyph="hot" tone="danger" note="Last week against what we projected.">Hot and cold</SimSectionTitle>
      {rows(hot, "hot", "Heating up", "danger")}
      {rows(cold, "cold", "Cooling off", "accent")}
      {rows(wire, "waiver", "Hot on the wire", "success", true)}
    </AccentCard>
  );
}

/** The most interesting trade this week, then the latest moves around the league. */
export function SimLeagueMovesCard({ league, names, onTab }: { league: SimHomeResponse["league"]; names: Record<string, string>; onTab: OnTab }) {
  if (!league) return null;
  const spot = league.spotlight;
  if (!spot && league.recent.length === 0) return null;
  return (
    <AccentCard accent="var(--color-premium)" as="section">
      <SimSectionTitle glyph="league" tone="accent" note="What the other managers did lately.">Around the league</SimSectionTitle>
      {spot ? (
        <div className="flex flex-col gap-2 p-2" style={{ borderRadius: "var(--radius-card, 12px)", background: "color-mix(in srgb, var(--color-premium) 10%, transparent)" }} data-testid="trade-spotlight">
          <div className="flex items-center gap-2"><SimGlyph name="spark" size={14} /><ToneBadge label="Trade to know" color="var(--color-premium)" size="xs" /><span className="text-xs" style={{ color: "var(--color-text-muted)" }}>Week {spot.week}</span></div>
          <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-2">
            <SimTeamLink teamId={spot.team_a.team_id} name={spot.team_a.name} isYou={spot.team_a.is_you} size={32} stacked />
            <SimGlyph name="trade" size={18} />
            <SimTeamLink teamId={spot.team_b.team_id} name={spot.team_b.name} isYou={spot.team_b.is_you} size={32} stacked />
          </div>
          <p className="text-sm font-bold">{spot.headline}</p>
          <p className="text-xs" style={{ color: "var(--color-text-secondary)" }}>{spot.text}</p>
          <div className="flex flex-wrap gap-2">
            {spot.players.map((p) => (
              <span key={`${p.role}-${p.id}`} className="flex items-center gap-1"><ToneBadge label={p.role} color={p.role === "get" ? "var(--color-success)" : "var(--color-text-muted)"} size="xs" /><SimPlayerChip player={p} size={24} /></span>
            ))}
          </div>
        </div>
      ) : null}
      <ul className="flex flex-col" aria-label="Recent moves">
        {league.recent.map((m, i) => (
          <li key={i} className="flex items-start gap-2 py-1.5" style={{ borderTop: i > 0 ? "var(--border-width-default) solid var(--color-border)" : undefined }}>
            <SimTeamLink teamId={m.team_id} name={names[m.team_id] ?? "Team"} size={22} hideName />
            <span className="min-w-0 flex-1 text-xs" style={{ color: "var(--color-text-secondary)" }}>{m.text}</span>
            <ToneBadge label={`Wk ${m.week}`} color={simToneColor("muted")} size="xs" />
          </li>
        ))}
      </ul>
      <LinkButton onClick={() => onTab("league")}>See the full feed</LinkButton>
    </AccentCard>
  );
}
