"use client";

import { useMemo, useState, type ReactNode } from "react";

import type { DraftPickAsset } from "@/lib/api";
import { PillRow } from "@/components/PillRow";
import { ToneBadge } from "@/components/ToneBadge";
import { groupPicksForList, roundGroupDefaultOpen } from "@/lib/pickGroups";

/**
 * The one grouped draft-pick list. Year pills on top, then one collapsible
 * group per round with a count; long groups start collapsed. Every place
 * that lists picks (Draft Center, Trade Finder, Trade Analyzer) uses this and
 * supplies only the row via `renderPick`, so selection behaviour stays with
 * the caller. Mobile twin: mobile/src/components/PickGroupList.tsx.
 */
export function PickGroupList({
  picks,
  renderPick,
  selectedIds,
  emptyMessage = "No picks to show.",
  ariaLabel = "Draft pick years",
}: {
  picks: DraftPickAsset[];
  renderPick: (pick: DraftPickAsset) => ReactNode;
  /** Picks currently selected: counted on the round header and force that round open. */
  selectedIds?: ReadonlySet<string>;
  emptyMessage?: string;
  ariaLabel?: string;
}) {
  const seasons = useMemo(() => groupPicksForList(picks), [picks]);
  const [season, setSeason] = useState<string>("");
  const [toggled, setToggled] = useState<Record<string, boolean>>({});

  const active = seasons.find((group) => group.label === season) ?? seasons[0];

  if (!active) {
    return (
      <p className="text-sm py-2" style={{ color: "var(--color-text-muted)" }}>
        {emptyMessage}
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {seasons.length > 1 ? (
        <PillRow
          variant="scroll"
          ariaLabel={ariaLabel}
          options={seasons.map((group) => ({ label: `${group.label} (${group.count})`, value: group.label }))}
          active={active.label}
          onSelect={setSeason}
        />
      ) : null}
      <div className="flex flex-col gap-2">
        {active.rounds.map((group, index) => {
          const key = `${active.label}:${group.round}`;
          const defaultOpen = roundGroupDefaultOpen(group, index === 0, selectedIds);
          const open = toggled[key] ?? defaultOpen;
          const selectedCount = selectedIds ? group.picks.filter((pick) => selectedIds.has(pick.pick_id)).length : 0;
          return (
            <section key={key} className="glass-surface">
              <button
                type="button"
                aria-expanded={open}
                onClick={() => setToggled((prev) => ({ ...prev, [key]: !open }))}
                className="w-full flex items-center gap-2 px-3 py-2 text-left"
              >
                <span className="text-sm font-bold" style={{ color: "var(--color-text-primary)" }}>
                  {group.label}
                </span>
                <ToneBadge label={`${group.picks.length} ${group.picks.length === 1 ? "pick" : "picks"}`} color="var(--color-information)" />
                {selectedCount > 0 ? <ToneBadge label={`${selectedCount} selected`} color="var(--color-success)" /> : null}
                <span aria-hidden className="ml-auto text-xs" style={{ color: "var(--color-text-muted)" }}>
                  {open ? "−" : "+"}
                </span>
              </button>
              {open ? (
                <div style={{ borderTop: "var(--border-width-default) solid var(--color-border)" }}>
                  {group.picks.map((pick) => (
                    <div key={pick.pick_id}>{renderPick(pick)}</div>
                  ))}
                </div>
              ) : null}
            </section>
          );
        })}
      </div>
    </div>
  );
}
