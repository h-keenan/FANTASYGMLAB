import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PrivacyModeToggle, PrivacyPill } from "./PrivacyMode";
import { PRIVACY_STORAGE_KEY, isPrivacyMode, resetPrivacyForTests, setPrivacyMode } from "@/lib/privacy";

beforeEach(() => {
  resetPrivacyForTests();
  window.localStorage.clear();
  Object.defineProperty(window, "location", { configurable: true, value: { ...window.location, reload: vi.fn() } });
});

describe("PrivacyPill", () => {
  it("renders nothing while off, and a tap-to-disable pill while on", () => {
    setPrivacyMode(true);
    render(<PrivacyPill />);
    fireEvent.click(screen.getByText("Privacy mode on"));
    expect(isPrivacyMode()).toBe(false);
    expect(window.location.reload).toHaveBeenCalled();
  });

  it("is hidden when off", () => {
    render(<PrivacyPill />);
    expect(screen.queryByText("Privacy mode on")).toBeNull();
  });
});

describe("PrivacyModeToggle", () => {
  it("persists the toggle and reloads so screens refetch masked", () => {
    render(<PrivacyModeToggle />);
    const toggle = screen.getByRole("switch", { name: "Privacy mode" });
    expect(toggle).toHaveAttribute("aria-checked", "false");
    fireEvent.click(toggle);
    expect(window.localStorage.getItem(PRIVACY_STORAGE_KEY)).toBe("1");
    expect(window.location.reload).toHaveBeenCalled();
  });
});
