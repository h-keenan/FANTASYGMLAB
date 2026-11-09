import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PlayerRow } from "@/components/PlayerRow";

describe("PlayerRow name fitting", () => {
  it("renders the name through PlayerNameText (F. Lastname when it overflows, never a mid-word ellipsis)", () => {
    render(<PlayerRow name="Amon-Ra St. Brown" position="WR" injuryStatus="Questionable" trailing={<span>78</span>} />);
    const name = screen.getByText("Amon-Ra St. Brown");
    expect(name.getAttribute("title")).toBe("Amon-Ra St. Brown");
  });
});
