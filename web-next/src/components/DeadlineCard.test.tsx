import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { DeadlineCard } from "@/components/DeadlineCard";

const win = (week: number | null, current: number | null, passed = false) => ({
  trade_deadline_week: week,
  current_week: current,
  trade_deadline_passed: passed,
});

describe("DeadlineCard", () => {
  it("frames a rebuilder's deadline as selling", () => {
    render(<DeadlineCard window={win(11, 9)} strategy="rebuild" />);
    expect(screen.getByText("Deadline in 2 weeks: sell aging depth")).toBeInTheDocument();
  });

  it("frames a contender's deadline as buying and links to ideas", () => {
    render(<DeadlineCard window={win(11, 10)} strategy="contender" href="/trade-hub/L1" ctaLabel="See ideas" />);
    expect(screen.getByText("Deadline in 1 week: buy a starter")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /See ideas/ })).toHaveAttribute("href", "/trade-hub/L1");
  });

  it("stays hidden when the deadline is further out than maxWeeksLeft", () => {
    render(<DeadlineCard window={win(11, 6)} strategy="contender" maxWeeksLeft={2} />);
    expect(screen.queryByTestId("deadline-card")).toBeNull();
  });

  it("renders nothing without a deadline or after it passed", () => {
    const { rerender } = render(<DeadlineCard window={win(null, 6)} strategy="contender" />);
    expect(screen.queryByTestId("deadline-card")).toBeNull();
    rerender(<DeadlineCard window={win(11, 12, true)} strategy="contender" />);
    expect(screen.queryByTestId("deadline-card")).toBeNull();
  });
});
