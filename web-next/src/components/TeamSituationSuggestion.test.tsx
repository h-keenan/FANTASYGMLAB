import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TeamSituationCard } from "./GmPlanSections";

function card(props: Partial<React.ComponentProps<typeof TeamSituationCard>>) {
  const onPick = vi.fn();
  render(<TeamSituationCard stance="" onPick={onPick} banner={null} pastDeadline={false} {...props} />);
  return onPick;
}

describe("Team Situation goal suggestion", () => {
  it("offers the stance the onboarding goal implies, but never applies it on its own", () => {
    const onPick = card({ suggestedStance: "rebuilding" });
    expect(screen.getByText(/set team situation to/i)).toHaveTextContent("Rebuilding");
    expect(onPick).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Set Rebuilding" }));
    expect(onPick).toHaveBeenCalledWith("rebuilding");
  });

  it("stays hidden once a stance is declared, or when no goal maps to one", () => {
    card({ stance: "competing", suggestedStance: "rebuilding" });
    expect(screen.queryByText(/set team situation to/i)).not.toBeInTheDocument();
  });

  it("shows nothing for a goal with no suggestion", () => {
    card({ suggestedStance: null });
    expect(screen.queryByText(/set team situation to/i)).not.toBeInTheDocument();
  });
});
