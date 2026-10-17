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
});
