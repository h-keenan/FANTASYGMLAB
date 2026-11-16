"use client";

import { CompactModule } from "@/components/ui/CompactModule";
import { CompactPlayerCard } from "@/components/ui/CompactPlayerCard";
import {
  depthChange,
  depthChartParts,
  depthRoleLabel,
  depthRowKind,
  injuryCoverageNote,
  injuryHistoryRows,
  injurySummaryParts,
  type DepthChartData,
  type InjuryRecordData,
} from "@/lib/playerDepthInjury";

/**
 * Depth chart section of the Player Quick View: the player's real NFL team at his slot, in the team's own order, his
 * row highlighted, with who is ahead and behind (each row opens that player's quick view) and any move since the
 * last weekly reading. Data-driven: it draws whatever `chart` it is given, so the Fantasy Sim's quick view can pass
 * a simulated chart. `chart === undefined` = loading; null / not on a chart renders nothing. Collapsed by default
 * (CompactModule). Mobile twin: mobile/src/components/PlayerDepthInjury.tsx.
 */
export function DepthChartSection({ chart, idPrefix = "pqv" }: { chart: DepthChartData | null | undefined; idPrefix?: string }) {
  if (chart === undefined) return <CompactModule id={`${idPrefix}.depth`} title="Depth chart" parts={[]} loading testId="pqv-depth-loading" />;
  const parts = depthChartParts(chart);
  if (!chart || parts.length === 0) return null;
  return (
    <CompactModule id={`${idPrefix}.depth`} title="Depth chart" label={`Depth chart, ${chart.slot_label ?? chart.slot ?? ""}`} parts={parts} tone="accent" testId="pqv-depth">
      <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        {chart.team} {chart.slot_label ?? chart.slot} · {chart.total} on the chart
      </p>
      <ol className="m-0 flex list-none flex-col gap-1 p-0" aria-label="Depth chart order">
        {chart.entries.map((entry) => {
          const kind = depthRowKind(entry, chart.self_order);
          const moved = depthChange(entry.change);
          const detail = [depthRoleLabel(chart.slot, entry.order), kind === "ahead" ? "Ahead" : kind === "behind" ? "Behind" : "This player", entry.injury_status]
            .filter(Boolean)
            .join(" · ");
          return (
            <li
              key={entry.player_id}
              data-testid="pqv-depth-row"
              data-kind={kind}
              aria-current={entry.is_self ? "true" : undefined}
              className="rounded-md px-1"
              style={entry.is_self ? { background: "color-mix(in srgb, var(--color-accent) 14%, transparent)", boxShadow: "inset 2px 0 0 var(--color-accent)" } : undefined}
            >
              <CompactPlayerCard
                player={{ id: entry.player_id, name: entry.name, position: entry.position, team: entry.team }}
                detail={detail}
                nonInteractive={entry.is_self ? "this is the player whose quick view is already open" : undefined}
                trailing={
                  moved ? (
                    <span style={{ color: moved.tone === "success" ? "var(--color-success)" : "var(--color-danger)" }} data-testid="pqv-depth-move">
                      {moved.arrow === "up" ? "▲" : "▼"} {moved.text}
                    </span>
                  ) : null
                }
              />
            </li>
          );
        })}
      </ol>
      <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>Order is the team&apos;s own listing; moves compare with last week.</p>
    </CompactModule>
  );
}

/**
 * Injury section: the current injury line ("Hamstring · Questionable") with practice status in the collapsed summary,
 * and on tap a compact history, one row per stint (season, injury, weeks, games missed) plus the career total.
 * `record === undefined` = loading; null renders nothing. Mobile twin: mobile/src/components/PlayerDepthInjury.tsx.
 */
export function InjuryHistorySection({ record, idPrefix = "pqv" }: { record: InjuryRecordData | null | undefined; idPrefix?: string }) {
  if (record === undefined) return <CompactModule id={`${idPrefix}.injury`} title="Injury history" parts={[]} loading testId="pqv-injury-loading" />;
  if (!record || !record.ok) return null;
  const rows = injuryHistoryRows(record);
  const note = injuryCoverageNote(record);
  const practice = record.current?.practice;
  const parts = injurySummaryParts(record);
  return (
    <CompactModule
      id={`${idPrefix}.injury`}
      title="Injury history"
      parts={practice ? [...parts.slice(0, 1), { key: "practice", text: practice, tone: "muted" }, ...parts.slice(1)] : parts}
      tone={record.current ? (record.current.unavailable ? "danger" : "warning") : "success"}
      testId="pqv-injury"
    >
      {record.current?.report ? <p className="text-sm">{record.current.report}</p> : null}
      {rows.length === 0 ? (
        <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>No missed games on record.</p>
      ) : (
        <table className="w-full border-collapse text-sm" data-testid="pqv-injury-rows">
          <thead>
            <tr className="text-left text-xs" style={{ color: "var(--color-text-muted)" }}>
              <th scope="col" className="py-1 font-bold">Season</th>
              <th scope="col" className="py-1 font-bold">Injury</th>
              <th scope="col" className="py-1 text-right font-bold">Missed</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.key} data-testid="pqv-injury-row">
                <td className="py-1 tabular-nums">{row.seasonLabel}</td>
                <td className="py-1">
                  {row.injury}
                  <span className="block text-xs" style={{ color: "var(--color-text-muted)" }}>{row.weeks}</span>
                </td>
                <td className="py-1 text-right tabular-nums">{row.games}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="font-extrabold">
              <td className="pt-2" colSpan={2}>Career games missed</td>
              <td className="pt-2 text-right tabular-nums" data-testid="pqv-injury-career">{record.career_games_missed}</td>
            </tr>
          </tfoot>
        </table>
      )}
      {note ? <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>{note}</p> : null}
    </CompactModule>
  );
}
