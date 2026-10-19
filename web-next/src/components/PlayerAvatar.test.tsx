import { render } from "@testing-library/react";
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

    expect(container.querySelector("span")).toHaveAttribute("title", "Impact Starter");
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
    expect(generational.container.querySelector("img")?.className).toContain("prestige-glow");

    const elite = render(<PlayerAvatar playerId="p1" tier="elite" />);
    expect(elite.container.querySelector("img")?.className).toContain("prestige-glow");

    const impactStarter = render(<PlayerAvatar playerId="p1" tier="impact_starter" />);
    expect(impactStarter.container.querySelector("img")?.className).toContain("prestige-glow");

    const starter = render(<PlayerAvatar playerId="p1" tier="starter" />);
    expect(starter.container.querySelector("img")?.className).not.toContain("prestige-glow");

    const noTier = render(<PlayerAvatar playerId="p1" />);
    expect(noTier.container.querySelector("img")?.className).not.toContain("prestige-glow");
  });
});
