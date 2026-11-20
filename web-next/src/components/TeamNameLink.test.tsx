import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/dynamic", () => ({
  default: () => (props: { teamName: string; rosterId: string | number }) => (
    <div data-testid="sheet">{`sheet ${props.teamName} ${props.rosterId}`}</div>
  ),
}));

import { TeamNameLink } from "@/components/TeamNameLink";

describe("TeamNameLink", () => {
  it("is a labelled 44px button that opens the team sheet", () => {
    render(<TeamNameLink leagueId="L1" rosterId="3" name="Just Win" />);
    const btn = screen.getByRole("button", { name: "Open Just Win team sheet" });
    expect(btn.style.minHeight).toBe("44px");
    expect(screen.queryByTestId("sheet")).toBeNull();
    fireEvent.click(btn);
    expect(screen.getByTestId("sheet").textContent).toBe("sheet Just Win 3");
  });

  it("renders plain without a roster or on the team's own page", () => {
    const { rerender } = render(<TeamNameLink leagueId="L1" rosterId={null} name="Just Win" />);
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.getByText("Just Win")).toBeTruthy();
    rerender(<TeamNameLink leagueId="L1" rosterId="3" name="Just Win" current />);
    expect(screen.queryByRole("button")).toBeNull();
  });
});
