import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { BeginnerHelp } from "./BeginnerHelp";
import { experienceCopy } from "@/lib/experienceCopy";

vi.mock("@/context/ExperienceLevelContext", () => ({
  useExperienceCopy: () => experienceCopy("beginner"),
}));

describe("BeginnerHelp", () => {
  it("never renders an orphan '?': inline mode shows its label next to the glyph", () => {
    const { container } = render(<BeginnerHelp label="live scoring" text="Scores update as games play." />);
    const root = container.querySelector("[data-beginner-help]") as HTMLElement;
    expect(root.textContent).toContain("?");
    expect(root.textContent).toContain("live scoring");
    expect(screen.getByRole("button", { name: "About live scoring" })).toBeInTheDocument();
  });

  it("popover mode still carries an accessible name and a close control", () => {
    render(<BeginnerHelp popover label="your game plan" text="Plan text." />);
    fireEvent.click(screen.getByRole("button", { name: "About your game plan" }));
    expect(screen.getByRole("dialog", { name: "your game plan" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Close explanation" }));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("requires a label at the type level", () => {
    // @ts-expect-error label is required: a bare '?' has no referent
    const el = <BeginnerHelp text="x" />;
    expect(el).toBeTruthy();
  });

  it("collapses several terms behind one labeled '?'", () => {
    render(<BeginnerHelp label="Value, Overall and Tier" lines={["A line.", null, "B line."]} />);
    expect(screen.getAllByRole("button", { name: /^About / })).toHaveLength(1);
  });
});
