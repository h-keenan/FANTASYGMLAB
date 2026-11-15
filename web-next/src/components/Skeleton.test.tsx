import { readFileSync } from "node:fs";
import path from "node:path";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LoadingScreen } from "@/components/LoadingScreen";
import { PageTabBarSkeleton } from "@/components/PageTabBar";
import { SkeletonAvatar, SkeletonList, SkeletonPage, SkeletonPlayerRow } from "@/components/Skeleton";
import { CompactModule } from "@/components/ui/CompactModule";
import { PlayerAccordionRowSkeleton } from "@/components/ui/PlayerAccordionRow";
import { StatusHeaderSkeleton } from "@/components/ui/StatusHeader";
import { TradeCompactCardSkeleton } from "@/components/ui/TradeCompactCard";
import { AVATAR_SIZE } from "@/lib/playerAnatomy";

describe("shared skeleton set", () => {
  it("draws the avatar circle at the density tier size", () => {
    const { container } = render(<SkeletonAvatar tier="card" />);
    const block = container.firstElementChild as HTMLElement;
    expect(block.style.width).toBe(`${AVATAR_SIZE.card}px`);
    expect(block.style.borderRadius).toContain("pill");
  });

  it("names a page once for screen readers and keeps its decorative parts hidden", () => {
    render(<LoadingScreen label="Players" layout="list" family="team" />);
    expect(screen.getAllByRole("status")).toHaveLength(1);
    expect(screen.getByRole("status", { name: "Loading Players" })).toBeTruthy();
    expect(screen.getAllByTestId("skeleton-player-row").length).toBeGreaterThan(3);
    expect(screen.getByTestId("skeleton-tabs").className).toContain("max-md:hidden");
  });

  it("has a content-shaped body per layout", () => {
    const layouts = { dashboard: "skeleton-status-header", list: "skeleton-player-row", cards: "skeleton-trade-card", detail: "skeleton-hero" } as const;
    for (const [layout, testId] of Object.entries(layouts)) {
      const { unmount } = render(<SkeletonPage label="x" layout={layout as keyof typeof layouts} />);
      expect(screen.getAllByTestId(testId).length).toBeGreaterThan(0);
      unmount();
    }
  });

  it("is the loading state of the shared templates", () => {
    render(
      <>
        <CompactModule id="t.loading" title="Waivers" loading />
        <PlayerAccordionRowSkeleton />
        <TradeCompactCardSkeleton />
        <StatusHeaderSkeleton label="Today" />
        <PageTabBarSkeleton family="trades" />
        <SkeletonList label="roster" count={2} />
        <SkeletonPlayerRow />
      </>,
    );
    expect(screen.getByRole("status", { name: "Loading Waivers" })).toBeTruthy();
    expect(screen.getByTestId("skeleton-module")).toBeTruthy();
    expect(screen.getByTestId("skeleton-trade-card")).toBeTruthy();
    expect(screen.getByTestId("skeleton-status-header")).toBeTruthy();
    expect(screen.getByTestId("player-accordion-row-skeleton")).toBeTruthy();
    expect(screen.getAllByTestId("skeleton-tabs")).toHaveLength(1);
  });

  it("shimmers with CSS that stops under prefers-reduced-motion", () => {
    const css = readFileSync(path.resolve(__dirname, "../app/globals.css"), "utf8");
    const reduced = css.match(/@media \(prefers-reduced-motion: reduce\) \{\s*\.pqv-skeleton-line,[^}]*animation: none;/);
    expect(reduced).not.toBeNull();
  });
});
