import { fireEvent, render } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PlayerAvatar } from "./PlayerAvatar";

// The headshot <img> has alt="" (decorative — the player's name is always
// shown as real text elsewhere in the row), which removes it from the
// accessibility tree, so these query the DOM directly rather than by role.
describe("PlayerAvatar", () => {
  it("titles the ring with the resolved tier's semantic label", () => {
    const { container } = render(<PlayerAvatar playerId="p1" tier="generational" />);

    expect(container.querySelector("img")).toHaveAttribute("title", "Generational");
  });

  it("omits the title when no caller passed a tier at all", () => {
    const { container } = render(<PlayerAvatar playerId="p1" />);

    expect(container.querySelector("img")).not.toHaveAttribute("title");
  });

  it("titles the no-photo fallback ring too", () => {
    const { container } = render(<PlayerAvatar playerId={null} tier="impact_starter" />);

    expect(container.querySelector("[data-avatar-fallback]")).toHaveAttribute("title", "Impact Starter");
  });

  // coridian_, 2026-10-18: "The prestige ring is still too small around
  // player PFP's" — a flat 2px border read fine at small list-row sizes
  // but was proportionally thin on PQV's 112px hero avatar.
  it("thickens the ring for larger hero-sized avatars without changing small list-row sizes", () => {
    const small = render(<PlayerAvatar playerId="p1" tier="starter" size={32} />);
    expect(small.container.querySelector("img")?.style.border).toContain("2px");

    const hero = render(<PlayerAvatar playerId="p1" tier="starter" size={112} />);
    expect(hero.container.querySelector("img")?.style.border).toContain("5px");
  });

  // coridian_, 2026-10-19 (queued cosmetic): only the top three tiers glow.
  it("glows the top three tiers, not starter and below", () => {
    const generational = render(<PlayerAvatar playerId="p1" tier="generational" />);
    expect(generational.container.querySelector(".prestige-glow > img")).not.toBeNull();

    const elite = render(<PlayerAvatar playerId="p1" tier="elite" />);
    expect(elite.container.querySelector(".prestige-glow > img")).not.toBeNull();

    const impactStarter = render(<PlayerAvatar playerId="p1" tier="impact_starter" />);
    expect(impactStarter.container.querySelector(".prestige-glow > img")).not.toBeNull();

    const starter = render(<PlayerAvatar playerId="p1" tier="starter" />);
    expect(starter.container.querySelector(".prestige-glow")).toBeNull();

    const noTier = render(<PlayerAvatar playerId="p1" />);
    expect(noTier.container.querySelector(".prestige-glow")).toBeNull();
  });

  // coridian_, "pqv still opens wrong" (2026-11-14): the PQV shell resizes the circle with CSS (112px full, 56px peek), and an
  // initials font computed from the `size` prop overflowed the smaller circle. The label scales with the circle's own box.
  it("sizes fallback initials from the circle's own box (container units), never from the size prop in px", () => {
    for (const size of [24, 56, 112]) {
      const { container, unmount } = render(<PlayerAvatar playerId={null} size={size} fallbackLabel="JS" />);
      const circle = container.querySelector<HTMLElement>("[data-avatar-fallback]")!;
      const label = container.querySelector<HTMLElement>("[data-avatar-initials]")!;
      expect(circle.style.containerType).toBe("inline-size");
      expect(circle.style.fontSize).toBe("");
      expect(label.getAttribute("style")).toContain("cqw");
      expect(label.textContent).toBe("JS");
      unmount();
    }
  });
});

describe("PlayerAvatar shape", () => {
  it("keeps a fixed circle that a narrow column cannot squash into an oval", () => {
    const { container } = render(<PlayerAvatar playerId="4046" size={40} />);
    const img = container.querySelector("img") as HTMLImageElement;
    expect(img.style.maxWidth).toBe("none");
    expect(img.style.flexShrink).toBe("0");
    expect(img.style.width).toBe(img.style.height);
  });

  // Batch F (2026-11): the fallback chain is headshot -> team logo (DEF) -> position-coloured monogram, never an empty disc.
  it("falls back to a monogram when the headshot fails to load", () => {
    const { container } = render(<PlayerAvatar playerId="4046" name="Patrick Mahomes" position="QB" />);
    fireEvent.error(container.querySelector("img")!);
    const disc = container.querySelector("[data-avatar-fallback]") as HTMLElement;
    expect(container.querySelector("img")).toBeNull();
    expect(disc.textContent).toBe("PM");
    expect(disc.style.color).toContain("--color-position-qb");
  });

  it("shows the team logo for a defense, then the monogram if the logo fails", () => {
    const { container } = render(<PlayerAvatar playerId="SF" name="49ers D/ST" position="DEF" team="SF" />);
    expect(container.querySelector("img")?.getAttribute("src")).toContain("team_logos/nfl/sf.png");
    fireEvent.error(container.querySelector("img")!);
    expect(container.querySelector("[data-avatar-fallback]")?.textContent).toBe("4D");
  });

  it("gives a made-up player (no id) initials, not an empty circle", () => {
    const { container } = render(<PlayerAvatar playerId={null} name="Ranked Player 0" position="WR" />);
    expect(container.querySelector("[data-avatar-fallback]")?.textContent).toBe("R0");
  });
});
