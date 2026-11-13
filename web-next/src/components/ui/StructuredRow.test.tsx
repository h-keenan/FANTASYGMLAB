import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { StructuredRow, StructuredRowList } from "./StructuredRow";

describe("StructuredRow", () => {
  it("is a plain, non-tappable row without detail or onOpen (no chevron, no button)", () => {
    render(<StructuredRow title="Team A" reason="One line" />);
    expect(screen.queryByRole("button")).toBeNull();
    expect(screen.getByText("One line")).toBeInTheDocument();
  });

  it("renders every field and opens its detail Sheet on tap, returning focus on close", () => {
    render(
      <StructuredRow
        title="Team A"
        chip={{ label: "Retool", color: "var(--color-warning)" }}
        pills={[{ key: "p", label: "Picks #10" }]}
        reason="Too few picks"
        detailTitle="Team A detail"
        detail={<p>Full sentence.</p>}
      />,
    );
    const row = screen.getByRole("button", { name: /Team A/ });
    expect(row).toHaveAttribute("aria-haspopup", "dialog");
    expect(screen.getByText("Picks #10")).toBeInTheDocument();
    row.focus();
    fireEvent.click(row);
    expect(screen.getByRole("dialog", { name: "Team A detail" })).toHaveTextContent("Full sentence.");
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    expect(row).toHaveFocus();
  });

  it("calls onOpen instead of opening a sheet", () => {
    const onOpen = vi.fn();
    render(<StructuredRow title="Team A" onOpen={onOpen} />);
    fireEvent.click(screen.getByRole("button"));
    expect(onOpen).toHaveBeenCalled();
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});

describe("StructuredRowList", () => {
  it("shows the top rows and toggles the rest", () => {
    render(<StructuredRowList items={[1, 2, 3, 4]} renderRow={(n) => <span>row {n}</span>} />);
    expect(screen.queryByText("row 4")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "See all (4)" }));
    expect(screen.getByText("row 4")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Show less" }));
    expect(screen.queryByText("row 4")).toBeNull();
  });
  it("renders nothing for an empty list and no toggle for a short one", () => {
    const { container, rerender } = render(<StructuredRowList items={[]} renderRow={() => null} />);
    expect(container).toBeEmptyDOMElement();
    rerender(<StructuredRowList items={[1, 2]} renderRow={(n) => <span>row {n}</span>} />);
    expect(screen.queryByRole("button")).toBeNull();
  });
});
