import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PlayerRow } from "@/components/PlayerRow";

describe("PlayerRow name wrapping", () => {
  it("wraps a long name instead of truncating it (phone-width audit, 2026-10)", () => {
    render(<PlayerRow name="Amon-Ra St. Brown" position="WR" injuryStatus="Questionable" trailing={<span>78</span>} />);
    const name = screen.getByText("Amon-Ra St. Brown");
    expect(name.className).not.toContain("truncate");
    expect(name.className).toContain("break-words");
  });
});
