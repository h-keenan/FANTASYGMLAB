"use client";

import { useCallback, useEffect, useMemo, useState, type CSSProperties } from "react";

import { Button, ButtonLink } from "@/components/Button";
import { PlayerAvatar } from "@/components/PlayerAvatar";
import { shareCardCacheKey } from "@/lib/shareCard/cacheKey";
import { useShareImage } from "@/lib/useShareImage";
import {
  normalizeWrappedDeck,
  wrappedGradeTone,
  wrappedPlayerLine,
  wrappedShareModel,
  wrappedShareText,
  wrappedShortName,
  wrappedView,
  type WrappedBlock,
  type WrappedCard,
  type WrappedDeck,
  type WrappedPlayer,
  type WrappedTone,
  type WrappedView,
} from "@/lib/wrapped";

const toneColor = (tone: WrappedTone): string => (tone === "good" ? "var(--color-success)" : tone === "warm" ? "var(--color-warning)" : "var(--color-text-secondary)");

const panel: CSSProperties = {
  background: "linear-gradient(165deg, rgba(50, 54, 60, 0.55), rgba(10, 12, 14, 0.9))",
  border: "1px solid var(--color-border)",
  borderRadius: "var(--radius-panel)",
  padding: 16,
};

const eyebrow: CSSProperties = { color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" };

function Face({ player, size = 44 }: { player: WrappedPlayer; size?: number }) {
  return <PlayerAvatar playerId={player.headshot_id} name={player.name} position={player.pos} team={player.team} size={size} />;
}

function PlayerHead({ player, size = 44 }: { player: WrappedPlayer; size?: number }) {
  return (
    <div className="flex items-center gap-3">
      <Face player={player} size={size} />
      <div className="min-w-0">
        <p className="truncate text-base font-extrabold">{wrappedShortName(player.name)}</p>
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>{[player.pos, player.team].filter(Boolean).join(" · ")}</p>
      </div>
    </div>
  );
}

function Chip({ label, tone }: { label: string; tone: WrappedTone }) {
  const color = toneColor(tone);
  return (
    <span className="inline-flex rounded-full px-3 py-1 text-xs font-bold" style={{ color, border: `1px solid ${color}`, background: "var(--color-surface-primary)" }}>
      {label}
    </span>
  );
}

function Rows({ rows }: { rows: { label: string; value: string }[] }) {
  if (!rows.length) return null;
  return (
    <dl className="flex flex-col gap-2 border-t pt-3" style={{ borderColor: "var(--color-border)" }}>
      {rows.map((r) => (
        <div key={r.label} className="flex items-baseline justify-between gap-3">
          <dt className="text-[11px] font-extrabold uppercase" style={eyebrow}>{r.label}</dt>
          <dd className="text-right text-sm font-bold tabular-nums">{r.value}</dd>
        </div>
      ))}
    </dl>
  );
}

function BlockPanel({ block }: { block: WrappedBlock }) {
  return (
    <div style={panel} className="flex flex-col gap-1">
      <div className="flex items-center justify-between gap-2">
        <span className="text-[11px] font-extrabold uppercase" style={eyebrow}>{block.label}</span>
        {block.badge ? <Chip label={block.badge} tone={block.tone} /> : null}
      </div>
      <p className="flex items-baseline gap-1 font-extrabold leading-none tabular-nums" style={{ fontSize: "var(--wrapped-hero, 56px)" }}>
        {block.hero}
        {block.unit ? <span className="text-base font-bold" style={{ color: "var(--color-text-muted)" }}>{block.unit}</span> : null}
      </p>
      {block.sub ? <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>{block.sub}</p> : null}
    </div>
  );
}

function Dots({ beat }: { beat: boolean[] }) {
  return (
    <div className="flex flex-wrap gap-1.5" aria-hidden>
      {beat.map((b, i) => (
        <span key={i} className="inline-block rounded-full" style={{ width: 12, height: 12, background: b ? "var(--color-accent)" : "transparent", border: "2px solid var(--color-accent)" }} />
      ))}
    </div>
  );
}

function Journey({ ranks, teams, note }: { ranks: number[]; teams: number; note: string }) {
  const w = 300;
  const h = 130;
  const step = ranks.length > 1 ? w / (ranks.length - 1) : w;
  const y = (r: number) => 8 + ((r - 1) / Math.max(1, teams - 1)) * (h - 16);
  const pts = ranks.map((r, i) => `${(i * step).toFixed(1)},${y(r).toFixed(1)}`).join(" ");
  const best = ranks.indexOf(Math.min(...ranks));
  return (
    <div style={panel} className="flex flex-col gap-2">
      <svg viewBox={`-6 0 ${w + 12} ${h}`} role="img" aria-label="League rank after each week" className="w-full">
        {[1, Math.ceil(teams / 2), teams].map((r) => (
          <g key={r}>
            <line x1="-6" x2={w + 6} y1={y(r)} y2={y(r)} stroke="var(--color-border)" strokeDasharray="3 4" />
            <text x="-4" y={y(r) - 3} fontSize="9" fill="var(--color-text-muted)">{r === 1 ? "1st" : `${r}th`}</text>
          </g>
        ))}
        <polyline points={pts} fill="none" stroke="var(--color-accent)" strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" />
        {best >= 0 ? <circle cx={best * step} cy={y(ranks[best])} r="4.5" fill="var(--color-success)" /> : null}
        <circle cx={(ranks.length - 1) * step} cy={y(ranks[ranks.length - 1])} r="4.5" fill="var(--color-accent)" />
      </svg>
      <p className="text-center text-xs" style={{ color: "var(--color-text-muted)" }}>{note}</p>
    </div>
  );
}

function LockedCard({ teaser, title }: { teaser: string; title: string }) {
  return (
    <div style={{ ...panel, borderColor: "var(--color-premium)" }} className="flex flex-col items-center gap-3 text-center" data-testid="wrapped-locked">
      <span className="flex h-9 w-9 items-center justify-center rounded-full" style={{ border: "1px solid var(--color-premium)", color: "var(--color-premium)" }} aria-hidden>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="5" y="11" width="14" height="9" rx="2" /><path d="M8 11V8a4 4 0 0 1 8 0v3" /></svg>
      </span>
      <span className="text-[11px] font-extrabold" style={{ color: "var(--color-premium)", letterSpacing: "var(--letter-spacing-badge)" }}>PRO</span>
      <p className="text-sm font-semibold">{teaser}</p>
      <div className="flex w-full flex-col gap-2" aria-hidden>
        <span className="h-2 rounded-full" style={{ background: "var(--color-surface-muted)" }} />
        <span className="h-2 w-2/3 self-center rounded-full" style={{ background: "var(--color-surface-muted)" }} />
      </div>
      <ButtonLink href="/premium" variant="premium" fullWidth aria-label={`Unlock ${title} with Pro`}>Unlock with Pro</ButtonLink>
    </div>
  );
}

function PersonaGlyph({ glyph }: { glyph: string }) {
  const path = glyph === "check" ? "M5 12l4 4 10-10" : glyph === "target" ? "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zm0 5a4 4 0 1 0 0 8 4 4 0 0 0 0-8z" : glyph === "clock" ? "M12 7v5l3 2M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z" : "M7 7h11l-3-3M17 17H6l3 3";
  return (
    <span className="flex h-14 w-14 items-center justify-center rounded-full" style={{ border: "1px solid var(--color-accent)", color: "var(--color-accent)", background: "var(--color-accent-soft)" }} aria-hidden>
      <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d={path} /></svg>
    </span>
  );
}

export function WrappedCardBody({ card }: { card: WrappedCard }) {
  const view: WrappedView = wrappedView(card);
  switch (view.kind) {
    case "locked":
      return <LockedCard teaser={view.teaser} title={card.title} />;
    case "hero":
      return (
        <div style={panel} className="flex flex-col gap-4" data-testid={`wrapped-${card.id}`}>
          {view.player ? <PlayerHead player={view.player} /> : null}
          <div className="flex flex-col items-center gap-2 py-2">
            <p className="flex items-baseline gap-1.5 font-extrabold leading-none tabular-nums" style={{ fontSize: view.hero.length > 6 ? 48 : 64 }}>
              {view.hero}
              {view.unit ? <span className="text-base font-bold" style={{ color: "var(--color-text-muted)" }}>{view.unit}</span> : null}
            </p>
            {view.chip ? <Chip label={view.chip} tone={view.chipTone} /> : null}
          </div>
          <Rows rows={view.rows} />
          {view.second ? (
            <div className="flex items-center gap-3 border-t pt-3" style={{ borderColor: "var(--color-border)" }}>
              <Face player={view.second} size={32} />
              <div className="min-w-0 text-xs">
                <p className="font-bold">{wrappedShortName(view.second.name)}</p>
                <p style={{ color: "var(--color-text-muted)" }}>{view.secondLabel} · {view.second.pos} · {view.second.team}</p>
              </div>
            </div>
          ) : null}
          {view.foot ? <p className="text-center text-xs" style={{ color: "var(--color-text-muted)" }}>{view.foot}</p> : null}
        </div>
      );
    case "blocks":
      return (
        <div className="flex flex-col gap-3" data-testid={`wrapped-${card.id}`}>
          <div className={view.blocks.length > 1 && card.id === "close" ? "grid grid-cols-2 gap-3" : "flex flex-col gap-3"} style={card.id === "close" ? ({ "--wrapped-hero": "36px" } as CSSProperties) : undefined}>
            {view.blocks.map((b) => <BlockPanel key={b.label} block={b} />)}
          </div>
          {view.rows.length || view.miss ? (
            <div style={panel} className="flex flex-col gap-3">
              <Rows rows={view.rows} />
              {view.miss ? (
                <div className="flex items-center gap-3">
                  <Face player={view.miss} size={36} />
                  <div className="min-w-0 text-xs">
                    <p className="text-[11px] font-extrabold uppercase" style={eyebrow}>Biggest miss</p>
                    <p className="font-bold">{wrappedPlayerLine(view.miss)}</p>
                    {view.missLine ? <p style={{ color: "var(--color-text-muted)" }}>{view.missLine}</p> : null}
                  </div>
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
      );
    case "dots":
      return (
        <div className="flex flex-col gap-3" data-testid="wrapped-consistency">
          {view.items.map((item, i) => (
            <div key={item.player.id} style={panel} className="flex flex-col gap-3">
              <p className="text-[11px] font-extrabold uppercase" style={eyebrow}>{i === 0 ? "Mr. Consistent" : "Rollercoaster"}</p>
              <div className="flex items-center justify-between gap-2">
                <PlayerHead player={item.player} size={36} />
                <Chip label={item.tally} tone="neutral" />
              </div>
              <Dots beat={item.beat} />
              <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>{item.caption}</p>
            </div>
          ))}
        </div>
      );
    case "trades":
      return (
        <div className="flex flex-col gap-3" data-testid="wrapped-trades">
          {view.sides.map((s, i) => (
            <div key={i} style={panel} className="flex flex-col gap-3">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-extrabold uppercase" style={eyebrow}>{i === 0 ? "Best trade" : "Worst trade"} · Wk {s.week}</span>
                <Chip label={s.grade} tone={wrappedGradeTone(s.grade)} />
              </div>
              {s.got.map((p) => (
                <div key={`g${p.id}`} className="flex items-center gap-2"><Face player={p} size={28} /><span className="text-sm font-bold">{wrappedShortName(p.name)}</span><span className="text-xs" style={{ color: "var(--color-text-muted)" }}>Got · {p.pos} · {p.team}</span></div>
              ))}
              {s.sent.map((p) => (
                <div key={`s${p.id}`} className="flex items-center gap-2"><Face player={p} size={28} /><span className="text-sm font-bold">{wrappedShortName(p.name)}</span><span className="text-xs" style={{ color: "var(--color-text-muted)" }}>Gave · {p.pos} · {p.team}</span></div>
              ))}
              <p className="rounded-full px-3 py-1 text-center text-xs font-bold" style={{ background: "var(--color-surface-primary)", color: i === 0 ? "var(--color-success)" : "var(--color-text-secondary)" }}>{s.net}</p>
            </div>
          ))}
        </div>
      );
    case "luck":
      return (
        <div style={panel} className="flex flex-col gap-4" data-testid="wrapped-luck">
          {[{ label: view.actualLabel, value: view.actual, color: "var(--color-text-muted)" }, { label: view.expectedLabel, value: view.expected, color: "var(--color-accent)" }].map((bar) => (
            <div key={bar.label} className="flex flex-col gap-1.5">
              <div className="flex items-baseline justify-between text-xs"><span style={{ color: "var(--color-text-secondary)" }}>{bar.label}</span><span className="font-bold tabular-nums">{Number.isInteger(bar.value) ? bar.value : bar.value.toFixed(1)}</span></div>
              <div className="h-2 rounded-full" style={{ background: "var(--color-surface-muted)" }}><div className="h-2 rounded-full" style={{ width: `${Math.min(100, (bar.value / view.max) * 100)}%`, background: bar.color }} /></div>
            </div>
          ))}
          <p className="self-center"><Chip label={view.chip} tone="neutral" /></p>
        </div>
      );
    case "journey":
      return <Journey ranks={view.ranks} teams={view.teams} note={view.note} />;
    case "grade":
      return (
        <div style={panel} className="flex flex-col items-center gap-4" data-testid="wrapped-grade">
          <div className="flex flex-col items-center gap-1">
            <span className="flex h-16 w-16 items-center justify-center rounded-full text-3xl font-extrabold" style={{ border: `2px solid ${toneColor(wrappedGradeTone(view.overall))}`, color: toneColor(wrappedGradeTone(view.overall)) }}>{view.overall}</span>
            <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>Overall</span>
          </div>
          <dl className="flex w-full flex-col gap-2">
            {view.subs.map((s) => (
              <div key={s.label} className="flex items-center justify-between">
                <dt className="text-[11px] font-extrabold uppercase" style={eyebrow}>{s.label}</dt>
                <dd className="flex h-7 min-w-7 items-center justify-center rounded-full px-2 text-xs font-extrabold" style={{ border: `1px solid ${toneColor(wrappedGradeTone(s.letter))}`, color: toneColor(wrappedGradeTone(s.letter)) }}>{s.letter}</dd>
              </div>
            ))}
          </dl>
        </div>
      );
    case "persona":
      return (
        <div style={panel} className="flex flex-col items-center gap-3 text-center" data-testid="wrapped-persona">
          <PersonaGlyph glyph={view.glyph} />
          <p className="text-2xl font-extrabold">{view.name}</p>
          <ul className="flex flex-col gap-1.5 text-xs" style={{ color: "var(--color-text-secondary)" }}>
            {view.lines.map((l) => <li key={l}>{l}</li>)}
          </ul>
          {view.runnerUp ? <Chip label={view.runnerUp} tone="neutral" /> : null}
        </div>
      );
  }
}

function ShareCardButton({ card, deck, itemId }: { card: WrappedCard; deck: WrappedDeck; itemId: string }) {
  const model = useMemo(() => wrappedShareModel(card, deck), [card, deck]);
  const share = useShareImage({
    cacheKey: shareCardCacheKey({ wrapped: model }),
    build: async () => {
      const { renderWrappedCardBlob } = await import("@/lib/shareCard/clientRender");
      return renderWrappedCardBlob(model);
    },
    filename: `fantasydesk-wrapped-${card.id}.png`,
    text: wrappedShareText(model),
    title: card.title,
    itemKind: "season_wrapped_card",
    leagueId: itemId,
  });
  return (
    <div className="flex flex-col gap-1">
      <Button variant="accentOutline" fullWidth onClick={share.onClick} disabled={share.busy}>{share.label("Share this card")}</Button>
      {share.status ? <span role="status" className="text-center text-xs" style={{ color: "var(--color-text-muted)" }}>{share.status}</span> : null}
    </div>
  );
}

/** The full-screen story: one card at a time, tap the sides or use the arrow keys to move, X to close. */
export function SeasonWrapped({ deck, itemId, onClose, startIndex = 0 }: { deck: WrappedDeck; itemId: string; onClose: () => void; startIndex?: number }) {
  const [index, setIndex] = useState(Math.max(0, Math.min(deck.cards.length - 1, startIndex)));
  const last = deck.cards.length - 1;
  const go = useCallback((delta: number) => setIndex((i) => Math.max(0, Math.min(last, i + delta))), [last]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      else if (e.key === "ArrowRight") go(1);
      else if (e.key === "ArrowLeft") go(-1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [go, onClose]);
  const card = deck.cards[index];
  const locked = card.locked || !card.data;
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={`${deck.partial ? "Season so far" : "Season wrapped"}, card ${index + 1} of ${deck.cards.length}`}
      className="fixed inset-0 z-[80] flex flex-col"
      style={{ background: "radial-gradient(120% 60% at 50% 0%, rgba(34, 211, 238, 0.14), transparent 60%), var(--color-bg)" }}
      data-testid="season-wrapped"
    >
      <div className="mx-auto flex w-full max-w-md flex-1 flex-col gap-4 px-4 pb-4 pt-3" style={{ minHeight: 0 }}>
        <div className="flex items-center gap-3">
          <div className="flex flex-1 gap-1" aria-hidden>
            {deck.cards.map((c, i) => (
              <span key={c.id} className="h-1 flex-1 rounded-full" style={{ background: i <= index ? "var(--color-accent)" : "var(--color-surface-raised)" }} />
            ))}
          </div>
          <button type="button" onClick={onClose} aria-label="Close" className="flex h-9 w-9 items-center justify-center rounded-full" style={{ border: "1px solid var(--color-border)", background: "var(--color-surface-primary)" }}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden><path d="M5 5l14 14M19 5L5 19" /></svg>
          </button>
        </div>
        <div className="relative flex flex-1 flex-col gap-5 overflow-y-auto" style={{ minHeight: 0 }}>
          <button type="button" className="absolute inset-y-0 left-0 z-10 w-1/4" aria-label="Previous card" onClick={() => go(-1)} disabled={index === 0} />
          <button type="button" className="absolute inset-y-0 right-0 z-10 w-1/4" aria-label="Next card" onClick={() => go(1)} disabled={index === last} />
          <header className="flex flex-col gap-1">
            <p className="text-[11px] font-extrabold uppercase" style={eyebrow}>{card.id === "intro" ? deck.season_label : card.eyebrow}</p>
            <h2 className="text-3xl font-extrabold leading-tight">{card.title}</h2>
            {card.sub ? <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>{card.sub}</p> : null}
          </header>
          <div className="my-auto" key={card.id}>
            <div className="enter-pop"><WrappedCardBody card={card} /></div>
          </div>
        </div>
        {locked ? <div style={{ height: 40 }} aria-hidden /> : <ShareCardButton card={card} deck={deck} itemId={itemId} />}
      </div>
    </div>
  );
}

/** A button that loads a deck and opens the story. `load` resolves the /wrapped body's deck (or null: nothing to wrap yet). */
export function SeasonWrappedLauncher({ label, itemId, load, variant = "secondary" }: { label: string; itemId: string; load: () => Promise<unknown>; variant?: "primary" | "secondary" | "accentOutline" }) {
  const [deck, setDeck] = useState<WrappedDeck | null>(null);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const open = async () => {
    setBusy(true);
    setNote(null);
    try {
      const parsed = normalizeWrappedDeck(await load());
      if (parsed) setDeck(parsed);
      else setNote("Nothing to wrap yet. Play a few more weeks.");
    } catch {
      setNote("Could not load your wrapped. Try again.");
    } finally {
      setBusy(false);
    }
  };
  const close = useCallback(() => setDeck(null), []);
  return (
    <>
      <div className="flex flex-col gap-1">
        <Button variant={variant} onClick={open} loading={busy}>{label}</Button>
        {note ? <span role="status" className="text-xs" style={{ color: "var(--color-text-muted)" }}>{note}</span> : null}
      </div>
      {deck ? <SeasonWrapped deck={deck} itemId={itemId} onClose={close} /> : null}
    </>
  );
}
