import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import DesignPage, { metadata } from "./page";
import robots from "../robots";
import sitemap from "../sitemap";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  usePathname: () => "/design",
  useSearchParams: () => new URLSearchParams(),
}));

describe("/design reference page", () => {
  it("is noindex and excluded from the sitemap", () => {
    expect(metadata.robots).toMatchObject({ index: false, follow: false });
    expect(sitemap().some((entry) => entry.url.includes("/design"))).toBe(false);
    const rules = robots().rules;
    const disallow = (Array.isArray(rules) ? rules[0] : rules).disallow;
    expect(disallow).toContain("/design");
  });

  it("renders every family with real components and no fetches", () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    render(<DesignPage />);
    for (const id of ["typography", "buttons", "badges", "rows", "cards", "tiles", "headers", "sheets", "forms", "states"]) {
      expect(screen.getByTestId(`family-${id}`)).toBeTruthy();
    }
    // Every family was consolidated (2026-10-23): no DUPLICATE flags should remain.
    expect(screen.queryAllByText("Duplicate")).toHaveLength(0);
    expect(fetchSpy).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
  });

  it("toggles the 390px frame", () => {
    render(<DesignPage />);
    const page = screen.getByTestId("design-page");
    expect(page.getAttribute("data-frame")).toBe("fluid");
    fireEvent.click(screen.getByRole("button", { name: "390px" }));
    expect(screen.getByTestId("design-page").getAttribute("data-frame")).toBe("390");
  });
});
