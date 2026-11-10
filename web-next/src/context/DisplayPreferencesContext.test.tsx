import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DisplayPreferencesProvider, useDisplayPreferences } from "./DisplayPreferencesContext";
import { OptionRadioGroup } from "@/components/OptionRadioGroup";
import { api } from "@/lib/api";
import {
  DENSITY_OPTIONS,
  DENSITY_STORAGE_KEY,
  THEME_BOOT_SCRIPT,
  THEME_OPTIONS,
  THEME_STORAGE_KEY,
  normalizeDensity,
  normalizeThemeMode,
  themeAttribute,
} from "@/lib/displayPreferences";

vi.mock("@/context/AuthContext", () => ({
  useAuth: () => ({ session: { user: { id: "user-1" } } }),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      getDevicePreferences: vi.fn(),
      updateDevicePreferences: vi.fn(),
    },
  };
});

function Probe() {
  const { density, showExplanations, themeMode, setThemeMode, setDensity, collegeInterest } = useDisplayPreferences();
  return (
    <div>
      <span data-testid="state">{`${density}|${showExplanations}|${themeMode}|${collegeInterest}`}</span>
      <button onClick={() => setThemeMode("light")}>day</button>
      <button onClick={() => setThemeMode("auto")}>auto</button>
      <button onClick={() => setDensity("compact")}>compact</button>
    </div>
  );
}

function prefs(over: Record<string, unknown> = {}) {
  return {
    ok: true,
    ui_density: "guided",
    theme_mode: "dark",
    theme_mode_set: false,
    experience_level: null,
    experience_goal: null,
    last_league: null,
    ...over,
  } as never;
}

describe("displayPreferences helpers", () => {
  it("normalizes unknown values to null", () => {
    expect(normalizeDensity("compact")).toBe("compact");
    expect(normalizeDensity("tiny")).toBeNull();
    expect(normalizeThemeMode("auto")).toBe("auto");
    expect(normalizeThemeMode(null)).toBeNull();
  });

  it("auto sets no data-theme attribute", () => {
    expect(themeAttribute("auto")).toBeNull();
    expect(themeAttribute("light")).toBe("light");
    expect(themeAttribute("dark")).toBe("dark");
  });

  it("offers the same options the app does", () => {
    expect(DENSITY_OPTIONS.map((o) => o.label)).toEqual(["Guided", "Compact"]);
    expect(THEME_OPTIONS.map((o) => o.label)).toEqual(["Night", "Day", "Auto"]);
  });

  it("boot script applies a stored forced theme before paint and ignores auto", () => {
    window.localStorage.setItem(THEME_STORAGE_KEY, "light");
    new Function(THEME_BOOT_SCRIPT)();
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    document.documentElement.removeAttribute("data-theme");
    window.localStorage.setItem(THEME_STORAGE_KEY, "auto");
    new Function(THEME_BOOT_SCRIPT)();
    expect(document.documentElement.hasAttribute("data-theme")).toBe(false);
  });
});

describe("DisplayPreferencesProvider", () => {
  beforeEach(() => {
    window.localStorage.clear();
    document.documentElement.removeAttribute("data-theme");
    vi.mocked(api.getDevicePreferences).mockReset();
    vi.mocked(api.updateDevicePreferences).mockReset().mockResolvedValue(prefs());
  });

  it("ignores the server's fallback theme when the account never picked one", async () => {
    vi.mocked(api.getDevicePreferences).mockResolvedValue(prefs({ ui_density: "compact" }));
    render(
      <DisplayPreferencesProvider>
        <Probe />
      </DisplayPreferencesProvider>,
    );
    await waitFor(() => expect(screen.getByTestId("state").textContent).toBe("compact|false|auto|on"));
    expect(document.documentElement.hasAttribute("data-theme")).toBe(false);
  });

  it("adopts a theme the account picked elsewhere (the app)", async () => {
    vi.mocked(api.getDevicePreferences).mockResolvedValue(prefs({ theme_mode: "light", theme_mode_set: true }));
    render(
      <DisplayPreferencesProvider>
        <Probe />
      </DisplayPreferencesProvider>,
    );
    await waitFor(() => expect(screen.getByTestId("state").textContent).toContain("|light|"));
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("light");
  });

  it("saves a choice locally, applies it, and syncs it to /v1/preferences", async () => {
    vi.mocked(api.getDevicePreferences).mockResolvedValue(prefs());
    render(
      <DisplayPreferencesProvider>
        <Probe />
      </DisplayPreferencesProvider>,
    );
    fireEvent.click(screen.getByText("day"));
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    expect(api.updateDevicePreferences).toHaveBeenCalledWith({ theme_mode: "light" });
    fireEvent.click(screen.getByText("auto"));
    expect(document.documentElement.hasAttribute("data-theme")).toBe(false);
    await act(async () => {
      fireEvent.click(screen.getByText("compact"));
    });
    expect(api.updateDevicePreferences).toHaveBeenCalledWith({ ui_density: "compact" });
    expect(window.localStorage.getItem(DENSITY_STORAGE_KEY)).toBe("compact");
    expect(screen.getByTestId("state").textContent).toBe("compact|false|auto|on");
  });
});

describe("OptionRadioGroup", () => {
  it("marks the selected option and reports a change", () => {
    const onChange = vi.fn();
    render(<OptionRadioGroup id="x" label="Density" options={DENSITY_OPTIONS} value="guided" onChange={onChange} />);
    expect(screen.getByRole("radio", { name: /Guided/ }).getAttribute("aria-checked")).toBe("true");
    fireEvent.click(screen.getByRole("radio", { name: /Compact/ }));
    expect(onChange).toHaveBeenCalledWith("compact");
  });
});
