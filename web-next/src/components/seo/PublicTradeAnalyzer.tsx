"use client";

import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";

import { ButtonLink, Button } from "@/components/Button";
import { Input } from "@/components/Input";
import { LeanBarMeter } from "@/components/LeanBarMeter";
import { PositionBadge } from "@/components/PositionBadge";
import { trackUse } from "@/lib/analytics";
import { formatTradeGain } from "@/lib/tradeHubPresentation";
import { storePendingBridgeTrade } from "@/lib/tradeBridge";
import {
  buildTradeSearch,
  ctaHref,
  evaluateTrade,
  MAX_ASSETS_PER_SIDE,
  parseTradeUrl,
  searchPlayers,
  TRADE_ANALYZER_PATH,
  valueOf,
  type TradeBoard,
  type TradeBoardPlayer,
  type TradeCta,
  type TradeSettings,
} from "@/lib/seo/tradeAnalyzer";
import { shareLinkWithUtm } from "@/lib/seo/tradeShare";

const FEATURE = "public_trade_analyzer";

function track(action: string, settings: TradeSettings, extra: Record<string, unknown> = {}) {
  trackUse(FEATURE, action, {
    props: {
      source_surface: FEATURE,
      league_format: settings.format === "superflex" ? "superflex" : "1qb",
      te_premium: settings.tep,
      ...extra,
    },
  });
}

/** Keep unrelated params (utm_*, ref) and replace only ours. */
export function mergeSearch(current: string, ours: string): string {
  const params = new URLSearchParams(current);
  for (const key of ["a", "b", "f", "tep"]) params.delete(key);
  const base = params.toString();
  const mine = ours.replace(/^\?/, "");
  const all = [base, mine].filter(Boolean).join("&");
  return all ? `?${all}` : "";
}

function PlayerLine({ player, settings }: { player: TradeBoardPlayer; settings: TradeSettings }) {
  return (
    <span className="flex min-w-0 flex-1 items-center gap-2">
      <PositionBadge position={player.pos} />
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-bold">{player.name}</span>
        <span className="block truncate text-xs" style={{ color: "var(--color-text-muted)" }}>
          {[player.team, player.age !== null ? `age ${player.age}` : null, player.inj].filter(Boolean).join(" · ")}
        </span>
      </span>
      <span className="text-sm font-bold" style={{ fontVariantNumeric: "tabular-nums" }}>
        {valueOf(player, settings).toLocaleString()}
      </span>
    </span>
  );
}

function SidePanel({
  title,
  hint,
  total,
  assets,
  board,
  settings,
  excludeIds,
  onAdd,
  onRemove,
}: {
  title: string;
  hint: string;
  total: number;
  assets: TradeBoardPlayer[];
  board: TradeBoard;
  settings: TradeSettings;
  excludeIds: ReadonlySet<string>;
  onAdd: (player: TradeBoardPlayer) => void;
  onRemove: (id: string) => void;
}) {
  const uid = useId();
  const listId = `${uid}-list`;
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const full = assets.length >= MAX_ASSETS_PER_SIDE;
  const results = useMemo(
    () => (open && !full ? searchPlayers(board.players, query, settings, excludeIds, 8) : []),
    [open, full, board.players, query, settings, excludeIds],
  );

  const choose = (player: TradeBoardPlayer) => {
    onAdd(player);
    setQuery("");
    setActive(0);
  };

  return (
    <section className="glass-surface flex flex-col gap-3 p-4" aria-labelledby={`${uid}-title`}>
      <div className="flex items-baseline justify-between gap-2">
        <h3 id={`${uid}-title`} style={{ font: "var(--type-section-title)" }}>
          {title}
        </h3>
        <span className="text-sm font-bold" style={{ fontVariantNumeric: "tabular-nums" }} aria-label={`${title} total value`}>
          {Math.round(total).toLocaleString()}
        </span>
      </div>
      <div className="relative">
        <Input
          type="text"
          role="combobox"
          aria-label={`Search players for ${title}`}
          aria-expanded={results.length > 0}
          aria-controls={listId}
          aria-autocomplete="list"
          aria-activedescendant={results.length > 0 ? `${listId}-${active}` : undefined}
          autoComplete="off"
          autoCorrect="off"
          spellCheck={false}
          enterKeyHint="search"
          placeholder={full ? `Up to ${MAX_ASSETS_PER_SIDE} players` : hint}
          disabled={full}
          value={query}
          className="w-full"
          onChange={(e) => {
            setQuery(e.target.value);
            setActive(0);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => setOpen(false)}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") {
              e.preventDefault();
              setOpen(true);
              setActive((i) => Math.min(i + 1, Math.max(results.length - 1, 0)));
            } else if (e.key === "ArrowUp") {
              e.preventDefault();
              setActive((i) => Math.max(i - 1, 0));
            } else if (e.key === "Enter" && results[active]) {
              e.preventDefault();
              choose(results[active]);
            } else if (e.key === "Escape") {
              setOpen(false);
            }
          }}
        />
        {results.length > 0 ? (
          <ul
            id={listId}
            role="listbox"
            aria-label={`${title} suggestions`}
            className="glass-surface absolute left-0 right-0 z-20 mt-1 max-h-72 overflow-auto"
            style={{ background: "var(--color-surface-raised)", border: "var(--border-width-default) solid var(--color-border-strong)" }}
          >
            {results.map((player, index) => (
              <li
                key={player.id}
                id={`${listId}-${index}`}
                role="option"
                aria-selected={index === active}
                className="flex min-h-[var(--touch-target-min)] cursor-pointer items-center px-3 py-2"
                style={index === active ? { background: "var(--color-accent-soft, var(--color-surface-muted))" } : undefined}
                // mousedown (not click) so the input's blur does not close the list first.
                onMouseDown={(e) => {
                  e.preventDefault();
                  choose(player);
                }}
                onMouseEnter={() => setActive(index)}
              >
                <PlayerLine player={player} settings={settings} />
              </li>
            ))}
          </ul>
        ) : null}
        {open && !full && query.trim() && results.length === 0 ? (
          <p className="mt-1 text-xs" style={{ color: "var(--color-text-muted)" }} role="status">
            No player found. Rookies and deep bench players may not be on the public board.
          </p>
        ) : null}
      </div>
      {assets.length === 0 ? (
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          No players added yet.
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {assets.map((player) => (
            <li
              key={player.id}
              className="flex items-center gap-2 px-2 py-1"
              style={{ background: "var(--color-surface-raised)", border: "var(--border-width-default) solid var(--color-border)" }}
            >
              <PlayerLine player={player} settings={settings} />
              <button
                type="button"
                onClick={() => onRemove(player.id)}
                aria-label={`Remove ${player.name} from ${title}`}
                className="inline-flex min-h-[var(--touch-target-min)] min-w-[var(--touch-target-min)] items-center justify-center text-lg font-bold"
                style={{ color: "var(--color-text-muted)" }}
              >
                <span aria-hidden="true">×</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

const GATE_FEATURES: { cta: Exclude<TradeCta, "verdict" | "sample">; title: string; body: string }[] = [
  {
    cta: "roster_impact",
    title: "Roster impact",
    body: "Checks your starting lineup this week: byes, injuries, and whether the trade leaves you without a startable RB, WR or QB.",
  },
  {
    cta: "partner_fit",
    title: "Partner fit",
    body: "Reads the other manager's roster and needs to tell you if they would actually say yes.",
  },
  {
    cta: "counter_offers",
    title: "Counter-offers",
    body: "Builds real alternate packages from the two rosters that grade as fair, picks included.",
  },
];

function GateCard({ onCta }: { onCta: (cta: TradeCta) => void }) {
  return (
    <section className="glass-surface flex flex-col gap-3 p-4" aria-labelledby="pta-gate-title" data-testid="trade-gate">
      <h3 id="pta-gate-title" style={{ font: "var(--type-section-title)" }}>
        This verdict is value-only. Get the roster-aware one.
      </h3>
      <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
        Totals can&apos;t see your team. A free FantasyDesk account connects your Sleeper league and adds:
      </p>
      <ul className="flex flex-col gap-2">
        {GATE_FEATURES.map((feature) => (
          <li key={feature.cta} className="flex gap-2 text-sm">
            <span
              className="mt-0.5 inline-flex h-5 shrink-0 items-center px-1.5 text-[0.65rem] font-bold uppercase"
              style={{ background: "var(--color-accent-soft, var(--color-surface-muted))", color: "var(--color-accent)", borderRadius: "var(--radius-pill)" }}
            >
              Free account
            </span>
            <span>
              <strong>{feature.title}.</strong>{" "}
              <span style={{ color: "var(--color-text-secondary)" }}>{feature.body}</span>
            </span>
          </li>
        ))}
      </ul>
      <ButtonLink
        href={ctaHref("verdict")}
        variant="primary"
        fullWidth
        onClick={() => onCta("verdict")}
      >
        Get a roster-aware verdict
      </ButtonLink>
      <ButtonLink href={ctaHref("sample")} variant="secondary" fullWidth onClick={() => onCta("sample")}>
        Try a sample league first
      </ButtonLink>
    </section>
  );
}

/** "Name and Name" / "Name, Name and 2 more", for the teaser's trade-specific lines. */
function nameList(players: readonly TradeBoardPlayer[], max = 2): string {
  const names = players.slice(0, max).map((p) => p.name);
  const rest = players.length - names.length;
  if (rest > 0) return `${names.join(", ")} and ${rest} more`;
  return names.length > 1 ? `${names.slice(0, -1).join(", ")} and ${names[names.length - 1]}` : names[0] ?? "";
}

/**
 * "Your roster" teaser, shown once a trade is entered. It says exactly what a
 * free account adds to THIS trade and carries the entered players through
 * sign-up (lib/tradeBridge.ts) so they are waiting in the logged-in analyzer.
 */
function RosterTeaser({
  sideA,
  sideB,
  onCta,
}: {
  sideA: readonly TradeBoardPlayer[];
  sideB: readonly TradeBoardPlayer[];
  onCta: (cta: TradeCta) => void;
}) {
  const sending = nameList(sideA);
  const getting = nameList(sideB);
  const items: { title: string; body: string }[] = [
    {
      title: "Roster-aware verdict",
      body: "Accept, counter, fair or decline for your team, instead of a value total that ignores who you already have.",
    },
    {
      title: "Lineup impact",
      body: `Whether sending ${sending} leaves a hole in your starting lineup this week, with byes and injuries counted.`,
    },
    {
      title: "Partner fit",
      body: `Whether the manager who has ${getting} would say yes, based on their roster and needs.`,
    },
    {
      title: "Counter-offers",
      body: "Real alternate packages from your two rosters if this one is not fair, picks included.",
    },
  ];
  return (
    <section className="glass-surface flex flex-col gap-3 p-4" aria-labelledby="pta-teaser-title" data-testid="roster-teaser">
      <h3 id="pta-teaser-title" style={{ font: "var(--type-section-title)" }}>
        Now see it on your roster
      </h3>
      <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
        This verdict is value-only, so it cannot see your team. A free FantasyDesk account connects your Sleeper league
        and adds, for this exact trade:
      </p>
      <ul className="flex flex-col gap-2">
        {items.map((item) => (
          <li key={item.title} className="flex gap-2 text-sm">
            <span aria-hidden="true" style={{ color: "var(--color-accent)" }}>
              ✓
            </span>
            <span>
              <strong>{item.title}.</strong> <span style={{ color: "var(--color-text-secondary)" }}>{item.body}</span>
            </span>
          </li>
        ))}
      </ul>
      <ButtonLink href={ctaHref("verdict")} variant="primary" fullWidth onClick={() => onCta("verdict")}>
        See how this trade affects MY team
      </ButtonLink>
      <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        Your player picks are kept in this browser for 24 hours so the trade is waiting after you connect a league.
        Players who are not on your league&apos;s rosters are flagged, not forced in.
      </p>
      <ButtonLink href={ctaHref("sample")} variant="secondary" fullWidth onClick={() => onCta("sample")}>
        Try a sample league first
      </ButtonLink>
    </section>
  );
}

export function PublicTradeAnalyzer() {
  const [board, setBoard] = useState<TradeBoard | null>(null);
  const [error, setError] = useState(false);
  const [settings, setSettings] = useState<TradeSettings>({ format: "1qb", tep: false });
  const [idsA, setIdsA] = useState<string[]>([]);
  const [idsB, setIdsB] = useState<string[]>([]);
  const [hydrated, setHydrated] = useState(false);
  const [copied, setCopied] = useState(false);
  const viewedRef = useRef(false);
  const restoredRef = useRef(false);

  const load = useCallback(() => {
    fetch("/api/public-trade-values")
      .then((r) => (r.ok ? (r.json() as Promise<TradeBoard>) : Promise.reject(new Error(String(r.status)))))
      .then((data) => {
        if (!Array.isArray(data.players) || data.players.length === 0) throw new Error("empty");
        // Restore a shared ?a=&b=&f=&tep= link once, as the values arrive.
        if (!restoredRef.current) {
          restoredRef.current = true;
          const initial = parseTradeUrl(window.location.search);
          setSettings(initial.settings);
          setIdsA(initial.a);
          setIdsB(initial.b);
        }
        setBoard(data);
        setHydrated(true);
      })
      .catch(() => setError(true));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const byId = useMemo(() => new Map((board?.players ?? []).map((p) => [p.id, p])), [board]);
  const effective: TradeSettings = useMemo(
    () => ({ format: settings.format, tep: settings.tep && Boolean(board?.tepAvailable) }),
    [settings, board],
  );
  const sideA = useMemo(() => idsA.map((id) => byId.get(id)).filter((p): p is TradeBoardPlayer => Boolean(p)), [idsA, byId]);
  const sideB = useMemo(() => idsB.map((id) => byId.get(id)).filter((p): p is TradeBoardPlayer => Boolean(p)), [idsB, byId]);
  const exclude = useMemo(() => new Set([...idsA, ...idsB]), [idsA, idsB]);
  const evaluation = useMemo(() => evaluateTrade(sideA, sideB, effective, board?.players ?? []), [sideA, sideB, effective, board]);

  // Shareable URL state (?a=&b=&f=&tep=), kept in sync without a navigation.
  useEffect(() => {
    if (!hydrated || !board) return;
    const next = buildTradeSearch({ a: sideA.map((p) => p.id), b: sideB.map((p) => p.id), settings: effective });
    try {
      window.history.replaceState(null, "", `${TRADE_ANALYZER_PATH}${mergeSearch(window.location.search, next)}`);
    } catch {
      // history API blocked: the tool still works, just not shareable.
    }
  }, [hydrated, board, sideA, sideB, effective]);

  const hasResult = evaluation.band !== "empty";
  useEffect(() => {
    if (hasResult && !viewedRef.current) {
      viewedRef.current = true;
      track("result_viewed", effective, { result: evaluation.band });
    }
  }, [hasResult, effective, evaluation.band]);

  const add = (side: "a" | "b") => (player: TradeBoardPlayer) => {
    const setter = side === "a" ? setIdsA : setIdsB;
    setter((ids) => (ids.includes(player.id) || ids.length >= MAX_ASSETS_PER_SIDE ? ids : [...ids, player.id]));
    track("player_added", effective, { destination: side === "a" ? "send" : "receive" });
  };
  const remove = (side: "a" | "b") => (id: string) =>
    (side === "a" ? setIdsA : setIdsB)((ids) => ids.filter((x) => x !== id));

  const setFormat = (format: TradeSettings["format"]) => {
    setSettings((s) => ({ ...s, format }));
    track("format_changed", { ...effective, format });
  };
  const toggleTep = (tep: boolean) => {
    setSettings((s) => ({ ...s, tep }));
    track("tep_toggled", { ...effective, tep });
  };

  const onCta = (cta: TradeCta) => {
    // The visitor's entered trade rides through sign-up and league connect
    // (the sample league is a fixed demo, so it carries nothing).
    if (cta !== "sample") storePendingBridgeTrade({ a: sideA.map((p) => p.id), b: sideB.map((p) => p.id) });
    track("cta_clicked", effective, { destination: cta === "sample" ? "sample_league" : "signup", item_kind: cta });
  };

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(shareLinkWithUtm(window.location.href));
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
      track("share_copied", effective);
    } catch {
      setCopied(false);
    }
  };

  const toneColor =
    evaluation.winner === "b" ? "var(--color-success)" : evaluation.winner === "a" ? "var(--color-danger)" : "var(--color-text-primary)";

  return (
    <div className="flex flex-col gap-4" data-testid="public-trade-analyzer">
      <div className="flex flex-wrap items-center gap-3">
        <div role="group" aria-label="League format" className="inline-flex" style={{ border: "var(--border-width-default) solid var(--color-border-strong)", borderRadius: "var(--radius-control)" }}>
          {(["1qb", "superflex"] as const).map((format) => {
            const on = settings.format === format;
            return (
              <button
                key={format}
                type="button"
                aria-pressed={on}
                onClick={() => setFormat(format)}
                className="min-h-[var(--touch-target-min)] px-4 text-sm font-bold"
                style={{
                  background: on ? "var(--color-accent-strong)" : "transparent",
                  color: on ? "var(--color-on-accent)" : "var(--color-text-primary)",
                  borderRadius: "var(--radius-control)",
                }}
              >
                {format === "1qb" ? "1QB" : "Superflex"}
              </button>
            );
          })}
        </div>
        <label className="inline-flex min-h-[var(--touch-target-min)] items-center gap-2 text-sm font-bold">
          <input
            type="checkbox"
            checked={effective.tep}
            disabled={!board?.tepAvailable}
            onChange={(e) => toggleTep(e.target.checked)}
            className="h-5 w-5"
          />
          Tight end premium
        </label>
      </div>

      {error ? (
        <div className="glass-surface flex flex-col gap-2 p-4" role="alert">
          <p className="text-sm">Player values did not load. Check your connection and try again.</p>
          <Button
            variant="secondary"
            onClick={() => {
              setError(false);
              load();
            }}
          >
            Retry
          </Button>
        </div>
      ) : !board ? (
        <div className="glass-surface p-4 text-sm" style={{ minHeight: "22rem", color: "var(--color-text-muted)" }} aria-busy="true">
          Loading player values...
        </div>
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-2">
            <SidePanel
              title="You send"
              hint="Search a player you would trade away"
              total={evaluation.totalA}
              assets={sideA}
              board={board}
              settings={effective}
              excludeIds={exclude}
              onAdd={add("a")}
              onRemove={remove("a")}
            />
            <SidePanel
              title="You get"
              hint="Search a player you would get back"
              total={evaluation.totalB}
              assets={sideB}
              board={board}
              settings={effective}
              excludeIds={exclude}
              onAdd={add("b")}
              onRemove={remove("b")}
            />
          </div>

          <section className="glass-surface flex flex-col gap-3 p-4" aria-live="polite" aria-label="Trade verdict" data-testid="trade-result">
            {hasResult ? (
              <>
                <p className="text-xs font-bold uppercase" style={{ color: "var(--color-text-muted)", letterSpacing: "0.03em" }}>
                  Value-only verdict
                </p>
                <div className="flex items-baseline justify-between gap-2">
                  <h3 className="text-xl font-black" style={{ color: toneColor }}>
                    {evaluation.headline}
                  </h3>
                  <span className="text-lg font-black" style={{ color: toneColor, fontVariantNumeric: "tabular-nums" }}>
                    {formatTradeGain(evaluation.diff)}
                  </span>
                </div>
                <LeanBarMeter sendScore={evaluation.totalA} receiveScore={evaluation.totalB} />
                <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
                  {evaluation.detail}
                </p>
                {evaluation.balancer ? (
                  <p className="text-sm">
                    <strong>To even it out,</strong>{" "}
                    {evaluation.winner === "a" ? "ask for" : "they would need to add"} about{" "}
                    {Math.abs(Math.round(evaluation.diff)).toLocaleString()} more value, roughly a player like{" "}
                    {evaluation.balancer.name} ({valueOf(evaluation.balancer, effective).toLocaleString()}).
                  </p>
                ) : null}
                {evaluation.caveats.map((caveat) => (
                  <p key={caveat} className="text-xs" style={{ color: "var(--color-warning)" }}>
                    {caveat}
                  </p>
                ))}
                <Button variant="secondary" size="sm" onClick={copyLink}>
                  {copied ? "Link copied" : "Copy share link"}
                </Button>
              </>
            ) : (
              <p className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
                {evaluation.headline}. {evaluation.detail}
              </p>
            )}
          </section>
          {hasResult ? <RosterTeaser sideA={sideA} sideB={sideB} onCta={onCta} /> : <GateCard onCta={onCta} />}
        </>
      )}
    </div>
  );
}
