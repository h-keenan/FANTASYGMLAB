import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { NotificationControls } from "./NotificationControls";

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  update: vi.fn(),
  rows: [] as Array<{ league_id: string; league_name: string | null }>,
}));

vi.mock("@/lib/supabase", () => ({
  supabase: {
    from: () => ({ select: () => ({ order: () => Promise.resolve({ data: mocks.rows, error: null }) }) }),
  },
}));
vi.mock("@/lib/api", () => ({
  api: {
    getNotificationPreferences: () => mocks.get(),
    updateNotificationPreferences: (patch: unknown) => mocks.update(patch),
  },
}));

function response(prefs: Record<string, unknown> = {}) {
  return {
    ok: true,
    categories: {},
    prefs: {
      quiet_hours_enabled: true,
      quiet_start: 22,
      quiet_end: 8,
      timezone: "",
      weekly_cap: null,
      league_overrides: {},
      category_modes: {},
      digest_hour: 8,
      critical_breaks_quiet: false,
      ...prefs,
    },
    default_weekly_cap: 4,
    cap_presets: [
      { key: "light", label: "Light", cap: 2 },
      { key: "standard", label: "Standard", cap: 4 },
      { key: "frequent", label: "Frequent", cap: 7 },
    ],
    critical_categories: ["injury", "lineup_lock", "trade_deadline"],
    league_modes: ["all", "critical", "mute"],
  };
}

describe("NotificationControls", () => {
  beforeEach(() => {
    mocks.rows = [
      { league_id: "L1", league_name: "Alpha" },
      { league_id: "L2", league_name: "Beta" },
    ];
    mocks.get.mockReset().mockResolvedValue(response());
    mocks.update.mockReset().mockImplementation((patch) => Promise.resolve(response(patch as Record<string, unknown>)));
  });

  it("renders nothing when the preferences cannot be read", async () => {
    mocks.get.mockResolvedValue({ ok: false });
    const { container } = render(<NotificationControls />);
    await waitFor(() => expect(mocks.get).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it("shows the server defaults: quiet hours on, Standard cap", async () => {
    render(<NotificationControls />);
    expect(await screen.findByText("Quiet hours")).toBeInTheDocument();
    expect(screen.getByLabelText("Quiet hours start")).toHaveValue("22");
    expect(screen.getByLabelText("Quiet hours end")).toHaveValue("8");
    expect(screen.getByRole("radio", { name: /Standard/ })).toHaveAttribute("aria-checked", "true");
  });

  it("saves a new cap preset", async () => {
    render(<NotificationControls />);
    fireEvent.click(await screen.findByRole("radio", { name: /Light/ }));
    await waitFor(() => expect(mocks.update).toHaveBeenCalledWith({ weekly_cap: 2 }));
  });

  it("turning the digest on batches only the non-urgent categories", async () => {
    render(<NotificationControls />);
    await screen.findByText("Batch non-urgent updates");
    const switches = screen.getAllByRole("switch");
    expect(switches).toHaveLength(3); // quiet hours, urgent-through, digest
    fireEvent.click(switches[2]);
    await waitFor(() => expect(mocks.update).toHaveBeenCalled());
    const patch = mocks.update.mock.calls[0][0] as { category_modes: Record<string, string> };
    expect(patch.category_modes.watch).toBe("digest");
    expect(patch.category_modes.injury).toBeUndefined();
  });

  it("mutes one league and reverts the UI when the save fails", async () => {
    render(<NotificationControls />);
    const select = await screen.findByLabelText("Notifications for Alpha");
    fireEvent.change(select, { target: { value: "mute" } });
    await waitFor(() => expect(mocks.update).toHaveBeenCalledWith({ league_overrides: { L1: "mute" } }));

    mocks.update.mockResolvedValue({ ok: false });
    fireEvent.change(screen.getByLabelText("Notifications for Beta"), { target: { value: "critical" } });
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not save");
    expect(screen.getByLabelText("Notifications for Beta")).toHaveValue("all");
  });

  it("hides the per-league section for a single league", async () => {
    mocks.rows = [{ league_id: "L1", league_name: "Alpha" }];
    render(<NotificationControls />);
    await screen.findByText("Quiet hours");
    expect(screen.queryByText("Per league")).not.toBeInTheDocument();
  });
});
