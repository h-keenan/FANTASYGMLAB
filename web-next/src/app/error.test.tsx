import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/lib/analytics", () => ({ trackClientError: vi.fn() }));
vi.mock("@/lib/errorReporter", () => ({ reportError: vi.fn() }));
vi.mock("next/image", () => ({ default: () => null }));

import AppError from "./error";
import GlobalError from "./global-error";
import { reportError } from "@/lib/errorReporter";

describe("error boundaries", () => {
  it("app/error shows a friendly screen, reports, and never renders the raw message", () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    const reset = vi.fn();
    const err = Object.assign(new Error("secret internal detail"), { digest: "abc123" });
    render(<AppError error={err} reset={reset} />);
    expect(screen.queryByText(/secret internal detail/)).toBeNull();
    expect(screen.getByText(/abc123/)).toBeTruthy();
    expect(reportError).toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(reset).toHaveBeenCalled();
  });

  it("global-error renders a self-contained recovery screen", () => {
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    // <html> inside a test container warns in jsdom; assert on content only.
    vi.spyOn(console, "warn").mockImplementation(() => undefined);
    const reset = vi.fn();
    render(<GlobalError error={new Error("boom")} reset={reset} />, { container: document });
    expect(screen.getByText("Something went wrong")).toBeTruthy();
    expect(screen.queryByText(/boom/)).toBeNull();
  });
});
