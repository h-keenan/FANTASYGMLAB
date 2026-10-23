import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { AccentCard } from "@/components/AccentCard";
import { Button } from "@/components/Button";
import { EmptyState } from "@/components/EmptyState";
import { SectionHeading } from "@/components/SectionHeading";
import { ToneBadge } from "@/components/ToneBadge";
import { ValueStat } from "@/components/ValueStat";
import { PickPlate, PickRow } from "@/components/PickRow";

describe("shared UI modules", () => {
  it("Button primary uses dark ink on the accent, never white", () => {
    render(<Button>Analyze</Button>);
    const style = screen.getByRole("button", { name: "Analyze" }).style;
    expect(style.color).toBe("var(--color-on-accent)");
    expect(style.background).toBe("var(--color-accent-strong)");
  });

  it("Button keeps a 44px touch target", () => {
    render(<Button size="sm">Tap</Button>);
    expect(screen.getByRole("button", { name: "Tap" }).className).toContain("min-h-[var(--touch-target-min)]");
  });

  it("EmptyState renders a next-step button that fires", () => {
    const onAction = vi.fn();
    render(<EmptyState title="Nothing here" subtitle="Add one." actionLabel="Add" onAction={onAction} />);
    fireEvent.click(screen.getByRole("button", { name: "Add" }));
    expect(onAction).toHaveBeenCalled();
  });

  it("ValueStat puts the Value caption above the number", () => {
    render(<ValueStat value={1234} />);
    const stat = screen.getByTestId("value-stat");
    expect(stat.firstElementChild?.textContent).toBe("Value");
    expect(stat.lastElementChild?.textContent).toBe("1,234");
  });

  it("ToneBadge is a rounded pill", () => {
    render(<ToneBadge label="You" color="var(--color-success)" />);
    expect(screen.getByText("You").style.borderRadius).toBe("var(--radius-pill)");
  });

  it("SectionHeading is uppercase", () => {
    render(<SectionHeading>Starters</SectionHeading>);
    expect(screen.getByRole("heading", { name: "Starters" }).className).toContain("uppercase");
  });

  it("AccentCard draws the semantic left rail", () => {
    render(<AccentCard accent="var(--color-warning)">Body</AccentCard>);
    expect(screen.getByText("Body").style.borderLeft).toContain("var(--color-warning)");
  });

  it("PickPlate shows round over pick number", () => {
    render(<PickPlate round={1} pickNo={3} />);
    expect(screen.getByText("R1")).toBeInTheDocument();
    expect(screen.getByText("#3")).toBeInTheDocument();
  });

  it("PickRow shows the round alone when no pick number, and a value only when given", () => {
    const { rerender } = render(<PickRow round={2} label="2027 Round 2" />);
    expect(screen.getByText("R2")).toBeInTheDocument();
    expect(screen.queryByText("#2")).not.toBeInTheDocument();
    expect(screen.queryByText("—")).not.toBeInTheDocument();
    rerender(<PickRow round={1} pickNo={3} label="2027 1st" value={5200} />);
    expect(screen.getByText("#3")).toBeInTheDocument();
    expect(screen.getByText("5,200")).toBeInTheDocument();
  });
});
