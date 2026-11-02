import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { rangeDisplayRows } from "@/lib/startSitRange";
import { RangeCompare } from "./RangeCompare";

const start = { name: "Boom Back", projected: 12.5, low: 4, high: 26 };
const over = { name: "Safe Back", projected: 12, low: 9, high: 15 };

describe("RangeCompare", () => {
  it("shows projected, low and high for both players and the lean with its why", () => {
    render(
      <RangeCompare
        rows={rangeDisplayRows(
          [
            { key: "start", label: "Start", range: start },
            { key: "over", label: "Over", range: over },
          ],
          "start",
        )}
        lean={{ kind: "ceiling", why: "You are a 20% underdog this week, so you need a big game." }}
      />,
    );
    expect(screen.getByText("Boom Back")).toBeTruthy();
    expect(screen.getByLabelText("High 26.0")).toBeTruthy();
    expect(screen.getByLabelText("Low 9.0")).toBeTruthy();
    expect(screen.getByText("Ceiling play")).toBeTruthy();
    expect(screen.getByText(/20% underdog/)).toBeTruthy();
    expect(screen.getByText(/typical-week range/)).toBeTruthy();
  });

  it("shows numbers but no lean badge when there is no lean", () => {
    render(<RangeCompare rows={rangeDisplayRows([{ key: "start", label: "Start", range: start }], null)} lean={null} />);
    expect(screen.queryByTestId("range-lean")).toBeNull();
    expect(screen.getByLabelText("Projected 12.5")).toBeTruthy();
  });

  it("renders nothing without any range", () => {
    const { container } = render(<RangeCompare rows={[]} lean={null} />);
    expect(container.innerHTML).toBe("");
  });
});
