import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import type { FilterGroup, FilterValues } from "@/lib/filterSheet";

import { FilterSheet } from "./FilterSheet";

const GROUPS: FilterGroup[] = [
  { id: "pos", label: "Position", anyValue: "ALL", options: [{ value: "ALL", label: "Any" }, { value: "QB", label: "QB" }, { value: "RB", label: "RB" }] },
  { id: "age", label: "Age", anyValue: "ALL", options: [{ value: "ALL", label: "Any age" }, { value: "29+", label: "29+" }] },
  { id: "tags", label: "Tags", multi: true, options: [{ value: "a", label: "Alpha" }, { value: "b", label: "Beta" }] },
];

function Harness({ initial = {}, count }: { initial?: FilterValues; count?: (v: FilterValues) => number }) {
  const [values, setValues] = useState<FilterValues>(initial);
  return <FilterSheet groups={GROUPS} values={values} onApply={setValues} resultCount={count} />;
}

describe("FilterSheet", () => {
  it("shows no badge with nothing active and a count badge with active filters", () => {
    const { rerender } = render(<FilterSheet groups={GROUPS} values={{}} onApply={() => {}} />);
    expect(screen.getByRole("button", { name: "Filters, none active" })).toBeInTheDocument();
    rerender(<FilterSheet groups={GROUPS} values={{ pos: ["QB"], tags: ["a", "b"] }} onApply={() => {}} />);
    expect(screen.getByRole("button", { name: "Filters, 3 active" })).toHaveTextContent("Filters3");
  });

  it("edits a draft and commits only on Apply", () => {
    const onApply = vi.fn();
    render(<FilterSheet groups={GROUPS} values={{}} onApply={onApply} />);
    fireEvent.click(screen.getByRole("button", { name: /Filters/ }));
    fireEvent.click(screen.getByRole("radio", { name: "QB" }));
    fireEvent.click(screen.getByRole("button", { name: "Beta" }));
    expect(onApply).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Apply" }));
    expect(onApply).toHaveBeenCalledWith({ pos: ["QB"], tags: ["b"] });
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("discards the draft when closed without Apply", () => {
    const onApply = vi.fn();
    render(<FilterSheet groups={GROUPS} values={{}} onApply={onApply} />);
    fireEvent.click(screen.getByRole("button", { name: /Filters/ }));
    fireEvent.click(screen.getByRole("radio", { name: "QB" }));
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    expect(onApply).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: /Filters/ }));
    expect(screen.getByRole("radio", { name: "QB" })).toHaveAttribute("aria-checked", "false");
    expect(screen.getByRole("radio", { name: "Any" })).toHaveAttribute("aria-checked", "true");
  });

  it("single-select groups pick one value, and tapping it again clears it", () => {
    render(<Harness />);
    fireEvent.click(screen.getByRole("button", { name: /Filters/ }));
    fireEvent.click(screen.getByRole("radio", { name: "QB" }));
    fireEvent.click(screen.getByRole("radio", { name: "RB" }));
    expect(screen.getByRole("radio", { name: "QB" })).toHaveAttribute("aria-checked", "false");
    expect(screen.getByRole("radio", { name: "RB" })).toHaveAttribute("aria-checked", "true");
    fireEvent.click(screen.getByRole("radio", { name: "RB" }));
    expect(screen.getByRole("radio", { name: "Any" })).toHaveAttribute("aria-checked", "true");
  });

  it("Reset clears the draft and the footer shows the live result count", () => {
    const count = (v: FilterValues) => (v.pos?.length ? 4 : 120);
    render(<Harness initial={{ pos: ["QB"] }} count={count} />);
    fireEvent.click(screen.getByRole("button", { name: /Filters/ }));
    expect(screen.getByRole("button", { name: "Show 4 results" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Reset" }));
    expect(screen.getByRole("button", { name: "Show 120 results" })).toBeInTheDocument();
  });

  it("disables Apply when the draft would match nothing", () => {
    render(<Harness count={() => 0} />);
    fireEvent.click(screen.getByRole("button", { name: /Filters/ }));
    expect(screen.getByRole("button", { name: "No results" })).toBeDisabled();
  });

  it("shows removable chips for active filters and removes one without opening the sheet", () => {
    render(<Harness initial={{ pos: ["QB"], tags: ["a"] }} />);
    expect(screen.getByLabelText("Active filters")).toHaveTextContent("QB");
    fireEvent.click(screen.getByRole("button", { name: "Remove Position filter: QB" }));
    expect(screen.queryByRole("button", { name: "Remove Position filter: QB" })).toBeNull();
    expect(screen.getByRole("button", { name: "Filters, 1 active" })).toBeInTheDocument();
  });
});
