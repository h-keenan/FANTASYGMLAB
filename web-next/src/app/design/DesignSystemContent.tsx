"use client";

import { useEffect, useState, type ReactNode } from "react";

import { AlertRow } from "@/components/AlertsContent";
import { Button, ButtonLink } from "@/components/Button";
import { ConfidenceMeter } from "@/components/ConfidenceMeter";
import { EmptyState } from "@/components/EmptyState";
import { ErrorState } from "@/components/ErrorState";
import { LeagueSwitcherButton } from "@/components/Header";
import { InfoTip } from "@/components/InfoTip";
import { LeanBarMeter } from "@/components/LeanBarMeter";
import { LoadingScreen } from "@/components/LoadingScreen";
import { OvrGauge } from "@/components/OvrGauge";
import { PickPlate, PickRow, draftPickRowProps } from "@/components/PickRow";
import { PillRow } from "@/components/PillRow";
import { PlayerInjuryBadge } from "@/components/PlayerInjuryBadge";
import { PqvBodySkeleton, StatGroup, SubRatingRow } from "@/components/PlayerQuickView";
import { PlayerIdentity, PlayerRow } from "@/components/PlayerRow";
import { PositionBadge } from "@/components/PositionBadge";
import { PremiumUpsellCard } from "@/components/PremiumUpsellCard";
import { SectionHeading } from "@/components/SectionHeading";
import { SheetHandle } from "@/components/SheetHandle";
import { SnapshotTile } from "@/components/SnapshotTile";
import { StatStrip } from "@/components/StatStrip";
import { ToneBadge } from "@/components/ToneBadge";
import { AccentCard } from "@/components/AccentCard";
import { ExchangeSide, TradeAssetRow } from "@/components/TradeAssetExchange";
import { TradeHubSkeleton } from "@/components/TradeHubFilters";
import { TradesTabBar } from "@/components/TradesTabBar";
import { ValueRing } from "@/components/ValueRing";
import { ValueStat } from "@/components/ValueStat";
import { VerdictCallout } from "@/components/VerdictCallout";
import type { AlertItem, DraftPickAsset, TradeAsset } from "@/lib/api";

import { applyThemeOverride, type ThemeChoice } from "./themeOverride";

/* ------------------------------------------------------------------ */
/* Static sample data. Nothing here touches the network.               */
/* ------------------------------------------------------------------ */

const PLAYER: TradeAsset = {
  asset_type: "player",
  name: "Jaxon Smith-Njigba",
  position: "WR",
  team: "SEA",
  age: 24,
  score: 8120,
  tier: "elite",
  overall_rating: 91,
};
const PLAYER_INJURED: TradeAsset = {
  asset_type: "player",
  name: "Christian McCaffrey",
  position: "RB",
  team: "SF",
  age: 30,
  score: 4310,
  tier: "starter",
  overall_rating: 78,
  injury_status: "Questionable",
};
const PICK_ASSET: TradeAsset = {
  asset_type: "pick",
  label: "2027 1st",
  round: "1",
  pick_no: 3,
  projected_range: "Early 1st",
  owner_team_name: "Gridiron Ghosts",
};
const DRAFT_PICK = {
  pick_id: "2027-1-1",
  label: "2027 Round 1",
  score: 5200,
  season: 2027,
  round: 1,
  original_roster_id: "1",
  owner_roster_id: "1",
  original_team_name: "Gridiron Ghosts",
  owner_team_name: "Gridiron Ghosts",
  pick_tier: "Premium",
  projected_pick_range: "Early 1st",
  projection_confidence: 0.64,
} as DraftPickAsset;
const ALERT: AlertItem = {
  title: "Tyreek Hill ruled out for Sunday",
  link: null,
  source: "Static sample",
  summary: "Expect a larger snap share for the WR2 behind him.",
  published_ts: null,
  event_type: "injury",
  speculative: false,
  alert_key: "design-1",
  read: false,
  matched_player: "Tyreek Hill",
  matched_player_id: null,
  matched_player_position: "WR",
  matched_player_team: "MIA",
  matched_player_tier: "starter",
  relevance_reason: null,
  roster_relationship: "starter",
};
const noop = () => {};

const POSITIONS = ["QB", "RB", "WR", "TE", "K", "DEF", "DL", "LB", "DB", "FLEX", "SUPER_FLEX", "IDP_FLEX", "BN", "IR"];

const SEMANTIC_COLORS: [string, string][] = [
  ["accent", "--color-accent"],
  ["success", "--color-success"],
  ["opportunity", "--color-opportunity"],
  ["action / premium", "--color-action"],
  ["warning", "--color-warning"],
  ["danger", "--color-danger"],
  ["diagnostic", "--color-diagnostic"],
  ["muted", "--color-muted"],
];
const SURFACE_COLORS: [string, string][] = [
  ["bg", "--color-bg"],
  ["surface-primary", "--color-surface-primary"],
  ["surface-raised", "--color-surface-raised"],
  ["surface-muted", "--color-surface-muted"],
  ["border", "--color-border"],
  ["border-strong", "--color-border-strong"],
  ["text-primary", "--color-text-primary"],
  ["text-secondary", "--color-text-secondary"],
  ["text-muted", "--color-text-muted"],
];
const TIER_COLORS: [string, string][] = [
  ["generational", "--color-tier-generational"],
  ["elite", "--color-tier-elite"],
  ["impact-starter", "--color-tier-impact-starter"],
  ["starter", "--color-tier-starter"],
  ["contributor", "--color-tier-contributor"],
  ["committee-role", "--color-tier-committee-role"],
  ["depth-dev", "--color-tier-depth-developmental"],
];
const TYPE_SCALE: [string, string][] = [
  ["--font-page-title (900 / 1.5rem)", "var(--font-page-title)"],
  ["--type-section-title (uppercase)", "var(--type-section-title)"],
  ["--font-card-title (800 / 0.875rem)", "var(--font-card-title)"],
  ["--type-primary-metric", "var(--type-primary-metric)"],
  ["body 0.875rem / 500", "var(--font-weight-body) var(--font-size-body) / var(--line-height-body) var(--font-family-sans)"],
  ["--type-caption-emphasis", "var(--type-caption-emphasis)"],
  ["--type-supporting-metadata", "var(--type-supporting-metadata)"],
];
const RADII: [string, string][] = [
  ["--radius-sm 10", "var(--radius-sm)"],
  ["--radius-control 14", "var(--radius-control)"],
  ["--radius-panel 20", "var(--radius-panel)"],
  ["--radius-pill", "var(--radius-pill)"],
  ["--radius-none 0 (PillRow, PickPlate)", "var(--radius-none)"],
];
const SPACING: [string, string][] = [
  ["2xs", "var(--space-2xs)"],
  ["xs", "var(--space-xs)"],
  ["sm", "var(--space-sm)"],
  ["md", "var(--space-md)"],
  ["lg", "var(--space-lg)"],
  ["xl", "var(--space-xl)"],
  ["2xl", "var(--space-2xl)"],
  ["3xl", "var(--space-3xl)"],
];

/* ------------------------------------------------------------------ */
/* Layout helpers                                                      */
/* ------------------------------------------------------------------ */

function Family({ id, title, note, children }: { id: string; title: string; note: string; children: ReactNode }) {
  return (
    <section id={id} className="flex flex-col gap-4" aria-labelledby={`${id}-h`} data-testid={`family-${id}`}>
      <div
        className="flex flex-col gap-1 pb-2"
        style={{ borderBottom: "var(--border-width-semantic) solid var(--color-accent)" }}
      >
        <h2
          id={`${id}-h`}
          className="uppercase"
          style={{ font: "var(--font-page-title)", letterSpacing: "var(--letter-spacing-eyebrow)" }}
        >
          {title}
        </h2>
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {note}
        </p>
      </div>
      {children}
    </section>
  );
}

/** A labeled specimen: the real component below a name + file path caption. */
function Spec({
  name,
  path,
  note,
  duplicate,
  children,
}: {
  name: string;
  path: string;
  note?: string;
  duplicate?: string;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-2" data-spec={name}>
      <div className="flex flex-col gap-0.5">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-extrabold" style={{ color: "var(--color-accent)" }}>
            {name}
          </span>
          {duplicate ? <DuplicateFlag /> : null}
        </div>
        <code className="text-[0.625rem] break-all" style={{ color: "var(--color-text-muted)" }}>
          {path}
        </code>
        {note ? (
          <span className="text-xs" style={{ color: "var(--color-text-secondary)" }}>
            {note}
          </span>
        ) : null}
        {duplicate ? (
          <span className="text-xs" style={{ color: "var(--color-warning)" }}>
            {duplicate}
          </span>
        ) : null}
      </div>
      <div className="flex flex-col gap-2">{children}</div>
    </div>
  );
}

function DuplicateFlag() {
  return (
    <span
      className="px-1.5 py-0.5 text-[0.625rem] font-black uppercase"
      style={{
        background: "var(--color-warning)",
        color: "#000",
        borderRadius: "var(--radius-pill)",
        letterSpacing: "var(--letter-spacing-badge)",
      }}
    >
      Duplicate
    </span>
  );
}

function Label({ children }: { children: ReactNode }) {
  return (
    <span
      className="uppercase text-[0.625rem] font-bold"
      style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}
    >
      {children}
    </span>
  );
}

function Variant({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-1 min-w-0">
      <Label>{label}</Label>
      {children}
    </div>
  );
}

function Swatch({ name, cssVar }: { name: string; cssVar: string }) {
  return (
    <div className="flex flex-col gap-1">
      <div
        style={{
          height: 36,
          background: `var(${cssVar})`,
          border: "var(--border-width-default) solid var(--color-border)",
          borderRadius: "var(--radius-sm)",
        }}
      />
      <span className="text-[0.625rem] leading-tight" style={{ color: "var(--color-text-secondary)" }}>
        {name}
      </span>
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

export function DesignSystemContent() {
  const [theme, setTheme] = useState<ThemeChoice>("auto");
  const [frame, setFrame] = useState(false);
  const [pill, setPill] = useState("a");
  const [pillFull, setPillFull] = useState("a");
  const [segment, setSegment] = useState("b");
  const [toggleOn, setToggleOn] = useState(true);

  useEffect(() => {
    applyThemeOverride(theme);
  }, [theme]);
  useEffect(() => () => applyThemeOverride("auto"), []);

  const pillOptions = [
    { label: "All", value: "a" },
    { label: "Starters", value: "b" },
    { label: "Bench", value: "c" },
  ];

  return (
    <main
      className="flex-1 flex flex-col gap-10 px-4 py-6 w-full mx-auto"
      style={{ maxWidth: frame ? 390 : 720 }}
      data-testid="design-page"
      data-frame={frame ? "390" : "fluid"}
    >
      <header className="flex flex-col gap-3">
        <span
          className="uppercase font-extrabold"
          style={{ font: "var(--type-supporting-metadata)", color: "var(--color-accent)", letterSpacing: "var(--letter-spacing-badge)" }}
        >
          Owner review / hidden
        </span>
        <h1 style={{ font: "var(--font-page-title)" }}>Design system reference</h1>
        <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          Every specimen is the real shared component with static sample data. Request changes by component name
          (per family, not per page). Items tagged DUPLICATE are near-copies to consolidate.
        </p>
        <div
          className="flex flex-wrap gap-3 p-3"
          style={{ border: "var(--border-width-default) solid var(--color-border)", background: "var(--color-surface-muted)" }}
        >
          <div className="flex flex-col gap-1">
            <Label>Theme</Label>
            <PillRow
              options={[
                { label: "Auto", value: "auto" },
                { label: "Light", value: "light" },
                { label: "Dark", value: "dark" },
              ]}
              active={theme}
              onSelect={(value) => setTheme(value as ThemeChoice)}
            />
          </div>
          <div className="flex flex-col gap-1">
            <Label>Frame</Label>
            <PillRow
              options={[
                { label: "Fluid", value: "fluid" },
                { label: "390px", value: "390" },
              ]}
              active={frame ? "390" : "fluid"}
              onSelect={(value) => setFrame(value === "390")}
            />
          </div>
        </div>
        <nav aria-label="Families" className="flex flex-wrap gap-x-3 gap-y-1 text-xs">
          {[
            ["typography", "Typography & tokens"],
            ["buttons", "Buttons"],
            ["badges", "Badges & chips"],
            ["rows", "Rows & lists"],
            ["cards", "Cards"],
            ["tiles", "Stat tiles & meters"],
            ["headers", "Headers"],
            ["sheets", "Sheets & overlays"],
            ["forms", "Forms"],
            ["states", "States"],
          ].map(([id, label]) => (
            <a key={id} href={`#${id}`} style={{ color: "var(--color-accent)" }}>
              {label}
            </a>
          ))}
        </nav>
      </header>

      {/* 1. TYPOGRAPHY & TOKENS */}
      <Family
        id="typography"
        title="Typography & tokens"
        note="Tokens live in web-next/src/app/globals.css (:root). Mobile mirrors them in mobile/src/theme.ts."
      >
        <Spec name="Type scale" path="web-next/src/app/globals.css (--font-*, --type-*)">
          {TYPE_SCALE.map(([label, font]) => (
            <div key={label} className="flex flex-col">
              <Label>{label}</Label>
              <span style={{ font, textTransform: label.includes("section") ? "uppercase" : undefined }}>
                Dynasty value looks strong
              </span>
            </div>
          ))}
        </Spec>
        <Spec name="Surface and text colors" path="globals.css (--color-bg ... --color-text-*)">
          <div className="grid grid-cols-3 gap-2">
            {SURFACE_COLORS.map(([name, cssVar]) => (
              <Swatch key={cssVar} name={name} cssVar={cssVar} />
            ))}
          </div>
        </Spec>
        <Spec
          name="Semantic lanes"
          path="globals.css (--color-accent/success/opportunity/action/warning/danger/diagnostic)"
          note="Fixed meanings: never repurpose a lane per screen."
        >
          <div className="grid grid-cols-4 gap-2">
            {SEMANTIC_COLORS.map(([name, cssVar]) => (
              <Swatch key={cssVar} name={name} cssVar={cssVar} />
            ))}
          </div>
        </Spec>
        <Spec name="Tier colors" path="globals.css (--color-tier-*)">
          <div className="grid grid-cols-4 gap-2">
            {TIER_COLORS.map(([name, cssVar]) => (
              <Swatch key={cssVar} name={name} cssVar={cssVar} />
            ))}
          </div>
        </Spec>
        <Spec name="Position colors" path="globals.css (--color-position-*)">
          <div className="grid grid-cols-5 gap-2">
            {["qb", "rb", "wr", "te", "k", "dst", "dl", "lb", "db", "flex"].map((p) => (
              <Swatch key={p} name={p.toUpperCase()} cssVar={`--color-position-${p}`} />
            ))}
          </div>
        </Spec>
        <Spec name="Radii" path="globals.css (--radius-*)">
          <div className="flex flex-wrap gap-3">
            {RADII.map(([label, value]) => (
              <div key={label} className="flex flex-col gap-1 items-start">
                <div
                  style={{
                    width: 56,
                    height: 40,
                    background: "var(--color-surface-raised)",
                    border: "var(--border-width-default) solid var(--color-border-strong)",
                    borderRadius: value,
                  }}
                />
                <span className="text-[0.625rem] max-w-[7rem]" style={{ color: "var(--color-text-secondary)" }}>
                  {label}
                </span>
              </div>
            ))}
          </div>
        </Spec>
        <Spec name="Spacing scale" path="globals.css (--space-*)">
          <div className="flex flex-col gap-1">
            {SPACING.map(([label, value]) => (
              <div key={label} className="flex items-center gap-2">
                <span className="text-[0.625rem] w-8" style={{ color: "var(--color-text-muted)" }}>
                  {label}
                </span>
                <span style={{ width: value, height: 10, background: "var(--color-accent)", display: "inline-block" }} />
              </div>
            ))}
          </div>
        </Spec>
        <Spec name="Tap target" path="globals.css (--touch-target-min, --control-min-height: 44px)" note="Every interactive control is at least 44px tall.">
          <div
            className="flex items-center justify-center text-xs font-bold"
            style={{
              minHeight: "var(--touch-target-min)",
              width: "var(--touch-target-min)",
              border: "var(--border-width-default) dashed var(--color-accent)",
              color: "var(--color-accent)",
            }}
          >
            44
          </div>
        </Spec>
      </Family>

      {/* 2. BUTTONS */}
      <Family id="buttons" title="Buttons" note="One Button/ButtonLink. Primary is dark ink on cyan; never white on cyan.">
        <Spec name="Button" path="web-next/src/components/Button.tsx" note="variant primary | secondary | ghost; size sm | md; fullWidth.">
          <div className="grid grid-cols-2 gap-3">
            <Variant label="Primary">
              <Button>Analyze trade</Button>
            </Variant>
            <Variant label="Secondary">
              <Button variant="secondary">Cancel</Button>
            </Variant>
            <Variant label="Ghost">
              <Button variant="ghost">View all</Button>
            </Variant>
            <Variant label="Danger (no variant exists)">
              <Button
                variant="secondary"
                style={{ color: "var(--color-danger)", borderColor: "var(--color-danger)" }}
              >
                Remove league
              </Button>
            </Variant>
            <Variant label="Disabled primary">
              <Button disabled>Analyze trade</Button>
            </Variant>
            <Variant label="Disabled secondary">
              <Button variant="secondary" disabled>
                Cancel
              </Button>
            </Variant>
            <Variant label="Loading (web has no loading prop)">
              <Button disabled>Working…</Button>
            </Variant>
            <Variant label="Size sm">
              <Button size="sm">Retry</Button>
            </Variant>
          </div>
          <Button fullWidth>Full width primary</Button>
        </Spec>
        <Spec name="ButtonLink" path="web-next/src/components/Button.tsx" note="The same look as a next/link.">
          <div className="flex flex-wrap gap-3">
            <ButtonLink href="/design#buttons">Primary link</ButtonLink>
            <ButtonLink href="/design#buttons" variant="secondary">
              Secondary link
            </ButtonLink>
            <ButtonLink href="/design#buttons" variant="ghost">
              Ghost link
            </ButtonLink>
          </div>
        </Spec>
      </Family>

      {/* 3. BADGES & CHIPS */}
      <Family id="badges" title="Badges & chips" note="Rounded pills. Position badges are the only fixed per-category tint set.">
        <Spec name="PositionBadge" path="web-next/src/components/PositionBadge.tsx" note="Every position incl. IDP and neutral lanes; sm and md; with rank.">
          <div className="flex flex-wrap gap-2">
            {POSITIONS.map((p) => (
              <PositionBadge key={p} position={p} />
            ))}
          </div>
          <div className="flex flex-wrap gap-2 items-center">
            {["QB", "RB", "WR", "TE"].map((p) => (
              <PositionBadge key={p} position={p} size="md" rank={12} />
            ))}
          </div>
        </Spec>
        <Spec
          name="ToneBadge vs PlayerInjuryBadge vs PositionBadge"
          path="components/ToneBadge.tsx | components/PlayerInjuryBadge.tsx | components/PositionBadge.tsx"
          duplicate="Three pill dialects: ToneBadge (text-xs, 15% tint, 0.085em tracking), PlayerInjuryBadge (0.625rem, own tint tokens, abbreviated code), PositionBadge (.position-badge CSS, min-width). Same family, three implementations."
        >
          <div className="flex flex-wrap items-center gap-2">
            <Variant label="ToneBadge">
              <div className="flex flex-wrap gap-2">
                <ToneBadge label="Starter" color="var(--color-success)" />
                <ToneBadge label="Bench" color="var(--color-opportunity)" />
                <ToneBadge label="Sell high" color="var(--color-warning)" />
                <ToneBadge label="Risk" color="var(--color-danger)" />
                <ToneBadge label="Premium" color="var(--color-premium)" />
                <ToneBadge label="Info" color="var(--color-information)" />
              </div>
            </Variant>
          </div>
          <div className="flex flex-wrap items-center gap-6">
            <Variant label="PlayerInjuryBadge">
              <div className="flex gap-2">
                <PlayerInjuryBadge status="Questionable" />
                <PlayerInjuryBadge status="Doubtful" />
                <PlayerInjuryBadge status="Out" />
                <PlayerInjuryBadge status="IR" />
                <PlayerInjuryBadge status="Suspended" />
              </div>
            </Variant>
            <Variant label="PositionBadge">
              <PositionBadge position="WR" />
            </Variant>
          </div>
        </Spec>
        <Spec name="Status tags (TRENDING / INJURY / WAIVER)" path="web-next/src/components/ToneBadge.tsx via lib/dashboardPresentation.ts watchTag" note="Watchlist tags are ToneBadge with fixed semantic colors.">
          <div className="flex flex-wrap gap-2">
            <ToneBadge label="Trending" color="var(--color-opportunity)" />
            <ToneBadge label="Injury" color="var(--color-danger)" />
            <ToneBadge label="Waiver" color="var(--color-action)" />
          </div>
        </Spec>
        <Spec name="PillRow (tab bar / segmented control)" path="components/PillRow.tsx" note="The only tab bar. Compact or fullWidth; options with href render as route tabs (TradesTabBar wraps it).">
          <Variant label="PillRow (compact)">
            <PillRow options={pillOptions} active={pill} onSelect={setPill} />
          </Variant>
          <Variant label="PillRow (fullWidth)">
            <PillRow options={pillOptions} active={pillFull} onSelect={setPillFull} fullWidth />
          </Variant>
          <Variant label="TradesTabBar (route tabs)">
            <TradesTabBar leagueId="sample" leagueName="Sample League" active="trade_hub" />
          </Variant>
        </Spec>
        <Spec name="InfoTip" path="web-next/src/components/InfoTip.tsx" note="Short label + info glyph; explanation opens on tap.">
          <InfoTip label="How is this calculated?">Static sample explanation text for the tip body.</InfoTip>
          <InfoTip label="Heads up" tone="warning">
            Warning-toned variant.
          </InfoTip>
        </Spec>
      </Family>

      {/* 4. ROWS & LISTS */}
      <Family id="rows" title="Rows & lists" note="Player identity is always PlayerRow/PlayerIdentity; pick assets always use PickPlate.">
        <Spec name="PlayerRow / PlayerIdentity" path="web-next/src/components/PlayerRow.tsx" note="Plain, with trailing gauge + ValueStat, injured, muted bench, and bordered list form.">
          <div className="glass-surface px-3 py-1 flex flex-col">
            <PlayerRow
              bordered
              name={PLAYER.name!}
              position="WR"
              tier="elite"
              trailing={
                <>
                  <OvrGauge rating={91} size="sm" />
                  <ValueStat value={8120} />
                </>
              }
            >
              SEA · Age 24
            </PlayerRow>
            <PlayerRow
              bordered
              name={PLAYER_INJURED.name!}
              position="RB"
              tier="starter"
              injuryStatus="Questionable"
              trailing={<ValueStat value={4310} />}
            >
              SF · Age 30
            </PlayerRow>
            <PlayerRow bordered muted name="Bench Guy" position="TE" tier="contributor" trailing={<ValueStat value="—" />}>
              DEN · Age 27
            </PlayerRow>
            <PlayerRow name="Idp Linebacker" position="LB" tier="starter" trailing={<ValueStat value={1900} />}>
              DAL · Age 26
            </PlayerRow>
          </div>
          <Variant label="PlayerIdentity only">
            <PlayerIdentity name="Josh Allen" position="QB" tier="generational" avatarSize={32}>
              BUF · Age 29
            </PlayerIdentity>
          </Variant>
        </Spec>
        <Spec name="PickRow" path="components/PickRow.tsx" note="The one pick row (square PickPlate). Value column only where the data has one; TradeAssetRow renders picks through it.">
          <Variant label="PickRow">
            <div className="glass-surface">
              <PickRow {...draftPickRowProps(DRAFT_PICK, true)} />
            </div>
          </Variant>
          <Variant label="TradeAssetRow (pick asset)">
            <div className="glass-surface px-3">
              <TradeAssetRow asset={PICK_ASSET} />
            </div>
          </Variant>
          <Variant label="PickPlate only">
            <div className="flex gap-2">
              <PickPlate round={1} pickNo={3} />
              <PickPlate round={2} />
              <PickPlate />
            </div>
          </Variant>
        </Spec>
        <Spec name="TradeAssetRow / ExchangeSide" path="web-next/src/components/TradeAssetExchange.tsx" note="Give/get columns with a faint tint of the side color.">
          <div className="grid grid-cols-1 gap-3">
            <ExchangeSide label="You send" dotColor="var(--color-danger)" assets={[PLAYER_INJURED, PICK_ASSET]} total={{ text: "6,310", color: "var(--color-danger)" }} />
            <ExchangeSide label="You get" dotColor="var(--color-success)" assets={[PLAYER]} total={{ text: "8,120", color: "var(--color-success)" }} />
          </div>
        </Spec>
        <Spec name="AlertRow" path="web-next/src/components/AlertsContent.tsx" note="Alert/news row: unread dot, relationship ToneBadge, identity chip, headline, summary.">
          <div className="glass-surface px-3">
            <AlertRow alert={ALERT} onOpen={noop} />
            <AlertRow alert={{ ...ALERT, alert_key: "design-2", read: true, title: "Read alert (dimmed)", roster_relationship: "bench", matched_player: null }} onOpen={noop} />
          </div>
        </Spec>
        <Spec
          name="Stat rows"
          path="web-next/src/components/PlayerQuickView.tsx (StatGroup)"
          note="Label / value / percentile band grid, shared with the Player Profile Stats tab."
        >
          <StatGroup
            title="Receiving"
            hideTitle
            items={[
              { label: "Rec", value: "94", note: "", percentile: 92 },
              { label: "Yds", value: "1,210", note: "", percentile: 71 },
              { label: "TD", value: "8", note: "", percentile: 48 },
              { label: "Targets", value: "132", note: "", percentile: 15 },
            ]}
          />
        </Spec>
      </Family>

      {/* 5. CARDS */}
      <Family id="cards" title="Cards" note="Every card sits on .glass-surface; AccentCard adds the semantic left rail.">
        <Spec name="AccentCard" path="web-next/src/components/AccentCard.tsx" note="accent = semantic token; compact = denser p-3.">
          <AccentCard accent="var(--color-success)">
            <span className="text-sm font-bold">Standard accent card (p-4)</span>
            <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
              Success lane. A fact or recommendation with a semantic edge.
            </span>
          </AccentCard>
          <AccentCard accent="var(--color-warning)" compact>
            <span className="text-sm font-bold">Compact accent card (p-3)</span>
          </AccentCard>
          <AccentCard accent="var(--color-danger)" compact>
            <span className="text-sm font-bold">Danger lane</span>
          </AccentCard>
        </Spec>
        <Spec name=".glass-surface" path="web-next/src/app/globals.css (.glass-surface)" note="The one card surface (radius-panel, glass fill).">
          <div className="glass-surface p-4 text-sm">Plain glass surface</div>
        </Spec>
        <Spec
          name="PremiumUpsellCard vs AccentCard"
          path="components/PremiumUpsellCard.tsx | components/AccentCard.tsx"
          duplicate="PremiumUpsellCard hand-rolls a square gold-bordered box (action-soft fill) instead of a glass AccentCard; mobile PremiumLock is a separate look again."
        >
          <PremiumUpsellCard
            bare
            kicker="Premium"
            upsell={null}
            fallbackTitle="Unlock Trade Finder"
            fallbackBody="Static sample copy for the lock card. Premium members get every trade partner ranked."
          />
        </Spec>
        <Spec
          name="EmptyState vs ErrorState vs bare muted text"
          path="components/EmptyState.tsx | components/ErrorState.tsx"
          duplicate="EmptyState is a left-aligned glass card; ErrorState is a centered full-page <main> with a bare red line; mobile EmptyState/ErrorState use centered icon circles. Several pages still use a bare muted <p>."
        >
          <EmptyState title="No trade ideas yet" subtitle="Check back after the next value refresh." actionLabel="Refresh" onAction={noop} />
        </Spec>
        <Spec name="VerdictCallout" path="web-next/src/components/VerdictCallout.tsx">
          <VerdictCallout color="var(--color-success)" label="You win" detail="+1,240 value" />
          <VerdictCallout color="var(--color-warning)" label="Close" detail="Within 3%" />
        </Spec>
      </Family>

      {/* 6. STAT TILES & METERS */}
      <Family id="tiles" title="Stat tiles & meters" note="Tiles show a number; meters show a magnitude. Colors are semantic, not decorative.">
        <Spec
          name="StatStrip / SnapshotTile vs ValueStat"
          path="components/StatStrip.tsx, components/SnapshotTile.tsx | components/ValueStat.tsx"
          duplicate="Two stat-tile dialects: SnapshotTile (glyph + label + value, tone) and ValueStat (caption-over-number, no container). Mobile adds MetricCard, StatStrip and DashboardStatRow."
        >
          <Variant label="StatStrip columns=4">
            <StatStrip
              columns={4}
              items={[
                { glyph: "record", label: "Record", value: "8-4" },
                { glyph: "power", label: "Power Rank", value: "#2", tone: "positive" },
                { glyph: "franchise", label: "Franchise Rank", value: "#1", tone: "premium" },
                { glyph: "age", label: "Avg Age", value: "26.4" },
              ]}
            />
          </Variant>
          <Variant label="StatStrip columns=3 (tones)">
            <StatStrip
              columns={3}
              items={[
                { glyph: "starter", label: "Starter", value: "#3", tone: "positive" },
                { glyph: "bench", label: "Bench", value: "#9", tone: "neutral" },
                { glyph: "injury", label: "Injuries", value: "2", tone: "risk" },
              ]}
            />
          </Variant>
          <Variant label="SnapshotTile (full, with note)">
            <SnapshotTile glyph="record" label="Record" value="8-4" note="Second best in the league" />
          </Variant>
          <Variant label="ValueStat">
            <div className="flex gap-6">
              <ValueStat value={8120} />
              <ValueStat value="—" align="left" />
            </div>
          </Variant>
        </Spec>
        <Spec
          name="ConfidenceMeter vs ValueRing vs OvrGauge"
          path="components/ConfidenceMeter.tsx | components/ValueRing.tsx | components/OvrGauge.tsx"
          duplicate="Confidence is drawn two ways: 3-segment bar (Waivers) and circular ring (Trade Hub). OvrGauge is a third circular gauge with its own tint ramp."
        >
          <Variant label="ConfidenceMeter">
            <div className="flex flex-col gap-1">
              <ConfidenceMeter label="Confidence" value="High" color="var(--color-success)" />
              <ConfidenceMeter label="Confidence" value="Medium" color="var(--color-warning)" />
              <ConfidenceMeter label="Confidence" value="Low" color="var(--color-danger)" />
            </div>
          </Variant>
          <Variant label="ValueRing (md low/mid/high, sm)">
            <div className="flex items-center gap-3">
              <ValueRing percent={22} tone="low" display="22" ariaLabel="low" />
              <ValueRing percent={55} tone="mid" display="55" ariaLabel="mid" />
              <ValueRing percent={88} tone="high" display="88" ariaLabel="high" />
              <ValueRing percent={88} tone="high" display="88" ariaLabel="small" size="sm" />
              <ValueRing percent={null} tone="mid" display="—" ariaLabel="none" />
            </div>
          </Variant>
          <Variant label="OvrGauge (sm / md / lg / empty)">
            <div className="flex items-center gap-3">
              <OvrGauge rating={91} size="sm" />
              <OvrGauge rating={64} size="md" />
              <OvrGauge rating={38} size="lg" />
              <OvrGauge rating={null} size="sm" />
            </div>
          </Variant>
        </Spec>
        <Spec name="LeanBarMeter (win-prob / value-edge bar)" path="web-next/src/components/LeanBarMeter.tsx" note="Center-anchored: right of the tick means you have the edge.">
          <Variant label="You have the edge">
            <LeanBarMeter sendScore={5000} receiveScore={7000} />
          </Variant>
          <Variant label="Even">
            <LeanBarMeter sendScore={5000} receiveScore={5000} />
          </Variant>
          <Variant label="Opponent has the edge">
            <LeanBarMeter sendScore={7000} receiveScore={4800} />
          </Variant>
        </Spec>
      </Family>

      {/* 7. HEADERS */}
      <Family id="headers" title="Headers" note="Section titles are uppercase with tight tracking; page titles use --font-page-title.">
        <Spec name="SectionHeading" path="web-next/src/components/SectionHeading.tsx" note="Plain, kicker + note, and with a right-aligned action.">
          <SectionHeading>Team Snapshot</SectionHeading>
          <SectionHeading kicker="Head-to-head" note="Based on current starters.">
            Matchup
          </SectionHeading>
          <SectionHeading action={<a className="text-xs font-bold" style={{ color: "var(--color-accent)" }} href="#headers">View all</a>}>
            Watchlist
          </SectionHeading>
        </Spec>
        <Spec name="Page header" path="web-next/src/components/Header.tsx (+ page-level h1 using --font-page-title)" note="App header is global; shown here is the page-title treatment pages use.">
          <div className="flex flex-col gap-1">
            <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
              Sample League
            </span>
            <h1 style={{ font: "var(--font-page-title)" }}>Page title</h1>
          </div>
        </Spec>
        <Spec name="LeagueSwitcherButton" path="web-next/src/components/Header.tsx" note="League switcher chip (tap to open the menu).">
          <div className="flex gap-2 flex-wrap">
            <LeagueSwitcherButton
              leagueId="a"
              leagueName="Sample Dynasty League"
              leagues={[
                { league_id: "a", league_name: "Sample Dynasty League" },
                { league_id: "b", league_name: "Second League" },
              ]}
            />
            <LeagueSwitcherButton leagueId="" leagueName={null} leagues={[]} />
          </div>
        </Spec>
      </Family>

      {/* 8. SHEETS & OVERLAYS */}
      <Family id="sheets" title="Sheets & overlays" note="Static previews (no fixed positioning). Real sheets are opened from player taps and menus.">
        <Spec
          name="Player Quick View sheet (.pqv-modal)"
          path="web-next/src/components/PlayerQuickView.tsx + globals.css (.pqv-modal, SheetHandle)"
          note="Static preview using the real shell classes and exported inner pieces."
        >
          <div className="relative overflow-hidden" style={{ background: "var(--color-scrim)", padding: "var(--space-lg)" }}>
            <div className="pqv-modal" style={{ width: "100%" }}>
              <SheetHandle />
              <div className="flex flex-col gap-3 p-4">
                <PlayerIdentity name={PLAYER.name!} position="WR" tier="elite" avatarSize={48}>
                  SEA · Age 24
                </PlayerIdentity>
                <SubRatingRow model={{ market_rating: 88, opportunity_rating: 90, scarcity_rating: 72, role_rating: 85, durability_rating: 60 }} />
              </div>
            </div>
          </div>
        </Spec>
        <Spec
          name="Modal backdrop: --color-scrim vs .pqv-backdrop"
          path="globals.css (--color-scrim 0.6 | .pqv-backdrop rgba(5,6,7,0.72))"
          duplicate="Owner decision 11 says one backdrop (--color-scrim). The PQV backdrop still hard-codes a darker 0.72 value."
        >
          <div className="grid grid-cols-2 gap-3">
            <Variant label="--color-scrim (0.6)">
              <div style={{ height: 80, background: "var(--color-scrim)", border: "var(--border-width-default) solid var(--color-border)" }} />
            </Variant>
            <Variant label=".pqv-backdrop (0.72)">
              <div className="pqv-backdrop" style={{ position: "relative", inset: "auto", height: 80, padding: 0, zIndex: 0 }} />
            </Variant>
          </div>
        </Spec>
        <Spec name="SheetHandle" path="web-next/src/components/SheetHandle.tsx" note="Grab bar, touch devices only (hidden on fine pointers).">
          <div className="pqv-modal" style={{ width: "100%", minHeight: 40 }}>
            <SheetHandle />
          </div>
        </Spec>
      </Family>

      {/* 9. FORMS */}
      <Family id="forms" title="Forms" note="Inputs use .glass-input with --radius-control; there is no shared Input/Toggle component yet.">
        <Spec name=".glass-input text input" path="web-next/src/app/globals.css (.glass-input)" note="Used by SignInForm and import forms; inputs are hand-assembled per form.">
          <input className="glass-input px-3 text-sm" style={{ minHeight: "var(--control-min-height)" }} placeholder="Sleeper username" aria-label="Sample input" />
          <input className="glass-input px-3 text-sm" style={{ minHeight: "var(--control-min-height)", borderColor: "var(--color-danger)" }} defaultValue="bad value" aria-label="Sample error input" />
          <select className="glass-input px-3 text-sm" style={{ minHeight: "var(--control-min-height)" }} aria-label="Sample select" defaultValue="a">
            <option value="a">Sample select</option>
            <option value="b">Option B</option>
          </select>
        </Spec>
        <Spec name="Segmented control" path="web-next/src/components/PillRow.tsx" note="PillRow is the only segmented control.">
          <PillRow options={pillOptions} active={segment} onSelect={setSegment} />
        </Spec>
        <Spec
          name="Toggle / switch"
          path="none shared (inline in ShareToCommunityToggle.tsx and settings forms)"
          duplicate="No shared Toggle component on web; each form hand-rolls a checkbox. Mobile uses the native Switch."
        >
          <label className="flex items-center gap-3 text-sm" style={{ minHeight: "var(--touch-target-min)" }}>
            <input type="checkbox" checked={toggleOn} onChange={() => setToggleOn((v) => !v)} />
            Share to community
          </label>
        </Spec>
      </Family>

      {/* 10. STATES */}
      <Family id="states" title="States" note="Loading, error and empty. Skeletons reserve the real layout height.">
        <Spec name="LoadingScreen" path="web-next/src/components/LoadingScreen.tsx" note="Branded splash with pulsing mark.">
          <div className="glass-surface flex" style={{ minHeight: 180 }}>
            <LoadingScreen status="Loading league…" />
          </div>
        </Spec>
        <Spec name="Skeletons" path="components/PlayerQuickView.tsx (PqvBodySkeleton) | components/TradeHubFilters.tsx (TradeHubSkeleton)" duplicate="Skeletons are written per layout (.pqv-skeleton-line reused, shapes re-declared in each). Mobile has SkeletonBlock/SkeletonCard/SkeletonRows.">
          <Variant label="PqvBodySkeleton">
            <div className="glass-surface p-3">
              <PqvBodySkeleton />
            </div>
          </Variant>
          <Variant label="TradeHubSkeleton (first card)">
            <div style={{ maxHeight: 240, overflow: "hidden" }}>
              <TradeHubSkeleton />
            </div>
          </Variant>
        </Spec>
        <Spec name="ErrorState" path="web-next/src/components/ErrorState.tsx" note="Message + Try again button.">
          <div className="glass-surface flex" style={{ minHeight: 160 }}>
            <ErrorState message="We could not load your league." onRetry={noop} />
          </div>
        </Spec>
        <Spec name="EmptyState" path="web-next/src/components/EmptyState.tsx">
          <EmptyState title="Nothing here yet" subtitle="Add a league to see your team." actionLabel="Connect league" onAction={noop} />
          <EmptyState title="No action available" subtitle="Title and subtitle only." />
        </Spec>
      </Family>

      <footer className="text-xs pb-8" style={{ color: "var(--color-text-muted)" }}>
        Hidden reference page (/design). Mobile counterpart: More screen, long-press the footer label.
      </footer>
    </main>
  );
}
