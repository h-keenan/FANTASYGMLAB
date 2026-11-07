import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PlayerNameText } from "@/components/PlayerNameText";

describe("PlayerNameText", () => {
  it("keeps a short name full", () => {
    render(<PlayerNameText name="Josh Allen" />);
    expect(screen.getByText("Josh Allen")).toBeTruthy();
  });

  it("abbreviates a long name but keeps the full name accessible", () => {
    render(<PlayerNameText name="Rhamondre Stevenson" />);
    const el = screen.getByText("R. Stevenson");
    expect(el.getAttribute("title")).toBe("Rhamondre Stevenson");
    expect(el.getAttribute("aria-label")).toBe("Rhamondre Stevenson");
    expect(el.className).toContain("truncate");
  });

  it("honors an Infinity threshold (measured-only)", () => {
    render(<PlayerNameText name="Quinshon Judkins" threshold={Infinity} />);
    expect(screen.getByText("Quinshon Judkins")).toBeTruthy();
  });
});
