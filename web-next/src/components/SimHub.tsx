"use client";

import { useMemo, useState } from "react";

import { AccentCard } from "@/components/AccentCard";
import { Button, ButtonLink } from "@/components/Button";
import { EmptyState } from "@/components/EmptyState";
import { PillRow } from "@/components/PillRow";
import { SimCrest } from "@/components/SimCrest";
import { SimProgressBar, simToneColor } from "@/components/SimGameParts";
import { ToneBadge } from "@/components/ToneBadge";
import { CompactModule } from "@/components/ui/CompactModule";
import { ConfirmInPlace } from "@/components/ui/ConfirmInPlace";
import { LetterGrade } from "@/components/ui/LetterGrade";
import { Sheet } from "@/components/ui/Sheet";
import { simGameLiteLine, simSetupBody, type SimGameCreateBody, type SimGameLite, type SimGameOptionsResponse, type SimSetupState } from "@/lib/simGame";
import { simHubRow } from "@/lib/simHub";
import { simHubGameName, simHubMode, simHubPresetChips, simHubPresets, type SimPresetId } from "@/lib/simHubPresets";
import type { SimGradeInput } from "@/lib/simGrade";

/**
 * The Fantasy Sim hub (docs/audits/ui-pass-3/sim-hub-options.html, V1). A "New game" button in the header opens a
 * presets sheet (Quick is preselected; Customize everything opens the full setup seeded with the preset). Saved games
 * are the page: one tappable row each (crest, name, shape, letter grade once finished, progress, phase), no chevrons.
 * First-timers get the explainer open and a nudge; returning players get it collapsed to one line. Mobile twin:
 * mobile/src/components/SimHub.tsx; presets and copy: lib/simHubPresets.ts.
 */
export function SimHub({
  games,
  options,
  block,
  isPremium,
  managing,
  deletingId,
  creating,
  onManage,
  onOpen,
  onDelete,
  onStart,
  onCustomize,
}: {
  games: SimGameLite[];
  options: SimGameOptionsResponse | null;
  /** Why New game is unavailable (the save limit), or null. */
  block: string | null;
  isPremium: boolean | undefined;
  managing: boolean;
  deletingId: string | null;
  creating: boolean;
  onManage: () => void;
  onOpen: (id: string) => void;
  onDelete: (id: string) => Promise<boolean>;
  onStart: (body: SimGameCreateBody) => void;
  onCustomize: (seed: SimSetupState) => void;
}) {
  const [sheetOpen, setSheetOpen] = useState(false);
  const mode = simHubMode(games.length);
  const first = mode === "first";
  return (
    <>
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-xl font-extrabold">Fantasy Sim</h2>
        <Button disabled={Boolean(block)} onClick={() => setSheetOpen(true)}>New game</Button>
      </div>
      {block ? (
        <div className="flex flex-col gap-2">
          <p className="text-xs" style={{ color: "var(--color-text-muted)" }} data-testid="new-game-block">{block}</p>
          <div className="flex flex-wrap items-center gap-2">
            {isPremium === false ? <ButtonLink href="/premium" variant="premiumOutline" size="sm">Go Pro</ButtonLink> : null}
            <Button variant="secondary" size="sm" onClick={onManage}>Manage games / delete one</Button>
          </div>
        </div>
      ) : null}
      <CompactModule
        id="sim.hub.about"
        title="What is this"
        label="What is Fantasy Sim"
        parts={[{ key: "line", text: "Be the GM. Win the season.", strong: true }, { key: "tags", text: "Draft, trade, recaps", tone: "muted" }]}
        defaultOpen={first}
        testId="sim-hub-about"
      >
        <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
          Draft a 12-team league against AI managers, set your lineup, work waivers and trades week by week, and take on the playoffs. At the end you get a grade. Nothing here touches your real leagues.
        </p>
      </CompactModule>
      <section id="sim-saved-games" className="flex flex-col gap-2" aria-label="Your games">
        <h3 className="text-[0.6875rem] font-extrabold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}>
          Your games{games.length ? ` · ${games.length}` : ""}
        </h3>
        {games.length === 0 ? (
          <EmptyState title="No games yet" subtitle="Tap New game and pick Quick. It takes about 10 minutes." />
        ) : (
          <>
            {managing ? <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>Tap the trash can on a game to delete it.</p> : null}
            {games.map((g) => (
              <div key={g.id} className="relative flex items-stretch gap-2">
                <button type="button" className="min-w-0 flex-1 text-left" onClick={() => onOpen(g.id)} aria-label={`Open game: ${simGameLiteLine(g)}`}>
                  <SavedGameRow game={g} />
                </button>
                <ConfirmInPlace
                  variant="icon"
                  overlay="parent"
                  label={`Delete game: ${simGameLiteLine(g)}`}
                  prompt="Delete this game? It can't be undone."
                  confirmLabel="Delete"
                  keepLabel="Keep"
                  errorText="Could not delete it. Try again."
                  disabled={deletingId !== null}
                  onConfirm={() => onDelete(g.id)}
                />
              </div>
            ))}
            <p className="text-center text-xs" style={{ color: "var(--color-text-muted)" }}>Tap a game to continue</p>
          </>
        )}
      </section>
      <NewGameSheet
        open={sheetOpen}
        options={options}
        creating={creating}
        onClose={() => setSheetOpen(false)}
        onStart={(body) => {
          setSheetOpen(false);
          onStart(body);
        }}
        onCustomize={(seed) => {
          setSheetOpen(false);
          onCustomize(seed);
        }}
      />
    </>
  );
}

function SavedGameRow({ game }: { game: SimGameLite }) {
  const row = simHubRow(game);
  const tone = row.chip.tone;
  const done = game.status === "complete";
  const grade: SimGradeInput | null = done && game.grade_letter ? { grade: game.grade_letter as SimGradeInput["grade"] } : null;
  const name = simHubGameName(game);
  return (
    <AccentCard accent={done ? simToneColor(tone) : "var(--color-accent)"} compact as="div">
      <div className="flex items-center gap-2.5">
        <SimCrest name={`${name} ${game.seed}`} size={34} />
        <span className="flex min-w-0 flex-1 flex-col">
          <span className="text-sm font-bold">{name}</span>
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>{row.meta.split(" · ").slice(1).join(" · ")}</span>
        </span>
        {grade ? <LetterGrade grade={grade} size="md" /> : null}
      </div>
      {row.progress ? <SimProgressBar done={row.progress.done} total={row.progress.total} tone={tone} label={`${row.progress.done} of ${row.progress.total} weeks played`} /> : null}
      <div className="flex items-center justify-between gap-2 text-xs" style={{ color: "var(--color-text-muted)" }}>
        <span className="inline-flex min-w-0 items-center gap-2">
          <ToneBadge label={done ? "Finished" : row.title} color={simToneColor(done ? "muted" : "accent")} size="xs" />
        </span>
        <span className="shrink-0">{row.played}{row.open ? <span className="font-bold" style={{ color: "var(--color-accent)" }}>{row.played ? " · " : ""}Continue</span> : null}</span>
      </div>
    </AccentCard>
  );
}

function NewGameSheet({
  open,
  options,
  creating,
  onClose,
  onStart,
  onCustomize,
}: {
  open: boolean;
  options: SimGameOptionsResponse | null;
  creating: boolean;
  onClose: () => void;
  onStart: (body: SimGameCreateBody) => void;
  onCustomize: (seed: SimSetupState) => void;
}) {
  const presets = useMemo(() => simHubPresets(options), [options]);
  const [picked, setPicked] = useState<SimPresetId>("quick");
  const preset = presets.find((p) => p.id === picked) ?? presets[0];
  const chips = simHubPresetChips(preset);
  return (
    <Sheet open={open} onClose={onClose} title="New game" size="sm" testId="sim-new-game-sheet">
      <div className="flex flex-col gap-3">
        {presets.length > 1 ? (
          <PillRow
            ariaLabel="Game preset"
            variant="fill"
            options={presets.map((p) => ({ label: p.label, value: p.id }))}
            active={preset.id}
            onSelect={(value) => setPicked(value as SimPresetId)}
          />
        ) : null}
        <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>{preset.blurb}</p>
        <div className="flex flex-wrap items-center gap-1.5" data-testid="sim-preset-chips">
          {chips.map((chip) => (
            <ToneBadge key={chip} label={chip} color="var(--color-accent)" size="xs" />
          ))}
        </div>
        <Button fullWidth disabled={creating} onClick={() => onStart(simSetupBody(preset.state))}>
          {creating ? "Starting..." : preset.action}
        </Button>
        <Button variant="ghost" fullWidth onClick={() => onCustomize(preset.state)}>
          Customize everything
        </Button>
      </div>
    </Sheet>
  );
}
