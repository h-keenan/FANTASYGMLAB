import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ModuleErrorBoundary } from "./ModuleErrorBoundary";

const reportError = vi.fn();
vi.mock("@/lib/errorReporter", () => ({ reportError: (...args: unknown[]) => reportError(...args) }));
vi.mock("@/lib/analytics", () => ({ trackClientError: vi.fn() }));

let shouldThrow = true;
function Bomb() {
  if (shouldThrow) throw new Error("x.map is not a function");
  return <p>module body</p>;
}

describe("ModuleErrorBoundary", () => {
  afterEach(() => {
    shouldThrow = true;
    reportError.mockClear();
  });

  it("shows a compact inline card for a failing module, reports it, and leaves siblings alone", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    render(
      <div>
        <p>sibling stays</p>
        <ModuleErrorBoundary name="demo">
          <Bomb />
        </ModuleErrorBoundary>
      </div>,
    );
    expect(screen.getByText("sibling stays")).toBeTruthy();
    expect(screen.getByTestId("error-state-compact")).toHaveTextContent("Couldn't load this");
    expect(screen.queryByText("x.map is not a function")).toBeNull();
    expect(reportError).toHaveBeenCalledTimes(1);
    expect(reportError.mock.calls[0][1]).toMatchObject({ source: "module_error_boundary", module: "demo" });
  });

  it("Retry remounts the module", () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    render(
      <ModuleErrorBoundary>
        <Bomb />
      </ModuleErrorBoundary>,
    );
    shouldThrow = false;
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(screen.getByText("module body")).toBeTruthy();
    expect(screen.queryByTestId("error-state-compact")).toBeNull();
  });

  it("renders children untouched when nothing throws", () => {
    shouldThrow = false;
    render(
      <ModuleErrorBoundary>
        <Bomb />
      </ModuleErrorBoundary>,
    );
    expect(screen.getByText("module body")).toBeTruthy();
  });
});
