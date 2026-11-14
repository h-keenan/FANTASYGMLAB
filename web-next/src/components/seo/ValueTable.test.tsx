import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ValueTable } from "./ValueTable";
import type { PublicPlayer } from "@/lib/seo/publicValues";

const player = { player_id: "1", name: "Test Player", position: "QB", team: "BUF", age: 30, score: 9000, trend: "Stable" } as unknown as PublicPlayer;

describe("ValueTable", () => {
  it("shows the trend as one glyph with an accessible label, not words that wrap the row", () => {
    const { container } = render(<ValueTable rows={[{ rank: 1, player, slug: null }]} valueHeader="Value" caption="x" />);
    expect(container.textContent).not.toContain("trend stable");
    expect(screen.getByRole("img", { name: "Workload trend: stable" }).textContent).toBe("→");
  });
});
