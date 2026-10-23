import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { PositionBadge } from "@/components/PositionBadge";
import { positionBadgeLabel, positionColorVar } from "@/lib/playerPresentation";

describe("PositionBadge pill", () => {
  it("renders a pill tinted by the position lane", () => {
    render(<PositionBadge position="rb" />);
    const el = screen.getByText("RB");
    expect(el.className).toContain("position-badge");
    expect(el.className).toContain("position-badge-sm");
    expect(el.style.getPropertyValue("--pb")).toBe("var(--color-position-rb)");
  });

  it("supports md size, rank suffix and renders nothing without a position", () => {
    const { container, rerender } = render(<PositionBadge position="WR" size="md" rank={12} />);
    expect(screen.getByText("WR12").className).toContain("position-badge-md");
    rerender(<PositionBadge position={null} />);
    expect(container.firstChild).toBeNull();
  });

  it("maps IDP and flex-type slots to lanes and short labels", () => {
    expect(positionColorVar("DL")).toBe("--color-position-dl");
    expect(positionColorVar("LB")).toBe("--color-position-lb");
    expect(positionColorVar("DB")).toBe("--color-position-db");
    for (const slot of ["FLEX", "SUPER_FLEX", "IDP_FLEX", "BN", "IR"]) {
      expect(positionColorVar(slot)).toBe("--color-position-flex");
    }
    expect(positionBadgeLabel("SUPER_FLEX")).toBe("SF");
    expect(positionBadgeLabel("IDP_FLEX")).toBe("IDP");
    expect(positionBadgeLabel("DST")).toBe("DEF");
  });
});
