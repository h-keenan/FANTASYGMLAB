"use client";

import type { ReactNode } from "react";

import { PlayerAvatar } from "@/components/PlayerAvatar";
import { PositionBadge } from "@/components/PositionBadge";
import { LetterGrade } from "@/components/ui/LetterGrade";
import type { SimGradeInput } from "@/lib/simGrade";
import type { SimDraftBarModel } from "@/lib/simDraft";

/**
 * The second line of the pinned draft bar (7a V1): the best available player with his avatar, position and letter grade
 * (ADP stays as the figure when the game has no grade). Tapping it opens the player. It is the `preview` of the Sim
 * draft-clock CompactModule, so it stays visible collapsed and expanded. Cyan / neutral only; gold is the clock's.
 */
export function SimDraftBar({ model, onOpen, grade, action }: { model: SimDraftBarModel; onOpen?: () => void; grade?: SimGradeInput | null; action?: ReactNode }) {
  const body = (
    <>
      <PlayerAvatar playerId={model.playerId} size={36} name={model.name} position={model.position} team={model.team} />
      <span className="flex min-w-0 flex-1 flex-col text-left">
        <span className="flex flex-wrap items-center gap-x-1.5">
          <span className="min-w-0 break-words text-sm font-bold">{model.name}</span>
          <PositionBadge position={model.position} />
        </span>
        <span className="line-clamp-2 text-xs" style={{ color: "var(--color-text-muted)" }}>
          {["Best available", model.adp, model.fit].filter(Boolean).join(" · ")}
        </span>
      </span>
      {grade?.grade ? <LetterGrade grade={grade} size="md" /> : null}
    </>
  );
  // ONE unit: photo, name, position, grade chip and the Draft button on a single row (the button sits beside the open-player target, not inside it).
  return (
    <div className="flex w-full items-center gap-2" data-testid="draft-bar">
      {onOpen ? (
        <button type="button" onClick={onOpen} className="flex min-w-0 flex-1 items-center gap-2" style={{ minHeight: "var(--touch-target-min)", color: "inherit" }} aria-label={`Best available: ${model.name}, ${model.position}${model.grade ? `, grade ${model.grade}` : ""}. Open player`} data-testid="draft-bar-player">
          {body}
        </button>
      ) : (
        <div className="flex min-w-0 flex-1 items-center gap-2" style={{ minHeight: "var(--touch-target-min)" }} data-testid="draft-bar-player">
          {body}
        </div>
      )}
      {action}
    </div>
  );
}
