"use client";

import { useEffect, useState, type CSSProperties } from "react";

import { Button } from "@/components/Button";
import { SimPlayerChip } from "@/components/SimGameParts";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import type { SimDraftPick } from "@/lib/simGame";
import { simMomentShortName, simPickBoardNote, simPickMomentGrade, simWeekStamp, type SimMomentTone } from "@/lib/simMoments";
import { useReducedMotion } from "@/lib/useMotion";
import { useSimCelebrations } from "@/lib/useSimCelebrations";

const eyebrow: CSSProperties = { color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" };
const toneColor = (tone: SimMomentTone): string => (tone === "good" ? "var(--color-success)" : tone === "warm" ? "var(--color-warning)" : "var(--color-text-secondary)");

function GradeDisc({ letter, tone, size = 56, pop = false }: { letter: string; tone: SimMomentTone; size?: number; pop?: boolean }) {
  return (
    <span
      className={`inline-flex items-center justify-center rounded-full font-extrabold ${pop ? "enter-pop" : ""}`}
      style={{ width: size, height: size, fontSize: size * 0.42, border: `2px solid ${toneColor(tone)}`, color: toneColor(tone), background: "var(--color-surface-primary)" }}
      data-testid="pick-grade"
    >
      {letter}
    </span>
  );
}

type Phase = "back" | "flip" | "front";

/**
 * The draft-pick moment: the card for your pick lands face down ("Tap to reveal your pick"), flips, and the grade pops in.
 * Your board so far sits underneath. Only mounted when Celebrations is on.
 */
export function SimPickReveal({ pick, board, onDone }: { pick: SimDraftPick; board: SimDraftPick[]; onDone: () => void }) {
  const reduced = useReducedMotion();
  const [phase, setPhase] = useState<Phase>(reduced ? "front" : "back");
  const grade = simPickMomentGrade(pick.value_over_adp);
  useEffect(() => {
    if (phase !== "flip") return;
    const id = setTimeout(() => setPhase("front"), 240);
    return () => clearTimeout(id);
  }, [phase]);
  const rows = board.slice(-3).reverse();
  const turn: CSSProperties = { transform: phase === "flip" ? "rotateY(90deg)" : "rotateY(0deg)", transition: "transform 240ms ease-in-out" };
  return (
    <div role="dialog" aria-modal="true" aria-label="Your pick" className="fixed inset-0 z-[70] flex items-center justify-center px-4" style={{ background: "rgba(0, 0, 0, 0.72)" }} data-testid="pick-reveal">
      <div className="flex w-full max-w-sm flex-col gap-4">
        <p className="text-xs font-extrabold uppercase" style={eyebrow}>Draft room · Round {pick.round}</p>
        <button
          type="button"
          onClick={() => phase === "back" && setPhase("flip")}
          disabled={phase !== "back"}
          aria-label={phase === "back" ? "Tap to reveal your pick" : `${pick.player.name}, grade ${grade.letter}`}
          className="glass-surface flex min-h-[260px] flex-col items-center justify-center gap-3 p-6 text-center"
          style={{ ...turn, perspective: 800 }}
        >
          {phase === "front" ? (
            <>
              <PlayerAvatar playerId={pick.player.headshot_id ?? null} name={pick.player.name} position={pick.player.pos} team={pick.player.team} size={64} />
              <span className="text-xl font-extrabold">{simMomentShortName(pick.player.name)}</span>
              <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>{[pick.player.pos, pick.player.team].filter(Boolean).join(" · ")} · Pick {pick.pick_no}</span>
              <GradeDisc letter={grade.letter} tone={grade.tone} pop />
              <span className="enter-pop rounded-full px-3 py-1 text-xs font-bold" style={{ border: `1px solid ${toneColor(grade.tone)}`, color: toneColor(grade.tone) }}>{grade.line}</span>
            </>
          ) : (
            <>
              <span className="text-[11px] font-extrabold uppercase" style={eyebrow}>Round {pick.round}</span>
              <span className="text-6xl font-extrabold">#{pick.pick_no}</span>
              <span className="text-sm" style={{ color: "var(--color-text-secondary)" }}>Tap to reveal your pick</span>
            </>
          )}
        </button>
        {rows.length ? (
          <section className="glass-surface flex flex-col gap-2 p-4" aria-label="Your board so far">
            <span className="text-[11px] font-extrabold uppercase" style={eyebrow}>Your board so far</span>
            {rows.map((r) => {
              const g = simPickMomentGrade(r.value_over_adp);
              return (
                <div key={r.pick_no} className="flex items-center gap-2">
                  <SimPlayerChip player={r.player} size={32} quick className="min-w-0 flex-1" extra={<span className="text-xs" style={{ color: "var(--color-text-muted)" }}>Rd {r.round}, #{r.pick_no}</span>} />
                  <div className="flex flex-col items-center">
                    <span className="inline-flex h-6 min-w-6 items-center justify-center rounded-full px-1.5 text-[11px] font-extrabold" style={{ border: `1px solid ${toneColor(g.tone)}`, color: toneColor(g.tone) }}>{g.letter}</span>
                    <span className="text-[11px]" style={{ color: "var(--color-text-muted)" }}>{simPickBoardNote(r.value_over_adp)}</span>
                  </div>
                </div>
              );
            })}
          </section>
        ) : null}
        <Button fullWidth variant={phase === "front" ? "primary" : "ghost"} onClick={onDone}>{phase === "front" ? "Continue" : "Skip"}</Button>
      </div>
    </div>
  );
}

const ROLL_MS = 900;

/**
 * The week moment, under the final score: "Scores rolling in..." while the numbers count up, then the win / loss stamp with the
 * record, the move in the standings and one line on why. Renders nothing when Celebrations is off (the plain result stays).
 */
export function SimWeekStamp({ recap }: { recap: Parameters<typeof simWeekStamp>[0] }) {
  const [on] = useSimCelebrations();
  const reduced = useReducedMotion();
  const stamp = simWeekStamp(recap);
  const [rolled, setRolled] = useState(reduced);
  useEffect(() => {
    if (reduced) return;
    const id = setTimeout(() => setRolled(true), ROLL_MS);
    return () => clearTimeout(id);
  }, [reduced]);
  if (!on || !stamp) return null;
  if (!rolled) return <p className="text-sm" style={{ color: "var(--color-text-secondary)" }} data-testid="week-rolling">Scores rolling in...</p>;
  return (
    <div className="flex flex-col items-center gap-2 enter-pop" data-testid="week-stamp">
      <span
        className="flex h-20 w-20 items-center justify-center rounded-full text-4xl font-extrabold"
        style={{ border: `4px solid ${toneColor(stamp.tone)}`, color: toneColor(stamp.tone), background: "var(--color-surface-primary)" }}
        aria-label={stamp.letter === "W" ? "Win" : stamp.letter === "L" ? "Loss" : "Tie"}
      >
        {stamp.letter}
      </span>
      <p className="text-base font-extrabold">{stamp.caption}</p>
      {stamp.note ? <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>{stamp.note}</p> : null}
    </div>
  );
}
