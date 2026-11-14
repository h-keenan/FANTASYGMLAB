"use client";

import { PlayerAvatar } from "@/components/PlayerAvatar";
import { PositionBadge } from "@/components/PositionBadge";
import type { SimDraftBarModel } from "@/lib/simDraft";

/**
 * The second line of the pinned draft bar (7a V1): the best available player with his avatar, position and letter grade
 * (ADP stays as the figure when the game has no grade). Tapping it opens the player. It is the `preview` of the Sim
 * draft-clock CompactModule, so it stays visible collapsed and expanded. Cyan / neutral only; gold is the clock's.
 */
export function SimDraftBar({ model, onOpen, grade }: { model: SimDraftBarModel; onOpen?: () => void; grade?: React.ReactNode }) {
  const body = (
    <>
      <PlayerAvatar playerId={model.playerId} size={36} fallbackLabel={model.name.trim().slice(0, 1)} />
      <span className="flex min-w-0 flex-1 flex-col text-left">
        <span className="text-[0.6875rem] font-extrabold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
          Best available
        </span>
        <span className="flex items-center gap-1.5">
          <span className="truncate text-sm font-bold">{model.name}</span>
          <PositionBadge position={model.position} />
        </span>
        {model.adp || model.fit ? (
          <span className="truncate text-xs" style={{ color: "var(--color-text-muted)" }}>
            {[model.adp, model.fit].filter(Boolean).join(" · ")}
          </span>
        ) : null}
      </span>
      {grade ?? (model.grade ? <GradeCapsule grade={model.grade} /> : null)}
    </>
  );
  return onOpen ? (
    <button type="button" onClick={onOpen} className="flex w-full items-center gap-2" style={{ minHeight: "var(--touch-target-min)", color: "inherit" }} aria-label={`Best available: ${model.name}, ${model.position}${model.grade ? `, grade ${model.grade}` : ""}. Open player`} data-testid="draft-bar-player">
      {body}
    </button>
  ) : (
    <div className="flex w-full items-center gap-2" style={{ minHeight: "var(--touch-target-min)" }} data-testid="draft-bar-player">
      {body}
    </div>
  );
}

function GradeCapsule({ grade }: { grade: string }) {
  return (
    <span role="img" aria-label={`Grade ${grade}`} data-testid="draft-bar-grade" className="inline-flex shrink-0 items-center justify-center text-base font-extrabold" style={{ minWidth: 40, height: 32, padding: "0 8px", borderRadius: "var(--radius-pill)", color: "var(--color-accent)", background: "color-mix(in srgb, var(--color-accent) 15%, transparent)", boxShadow: "inset 0 0 0 1.5px color-mix(in srgb, var(--color-accent) 55%, transparent)" }}>
      {grade}
    </span>
  );
}
