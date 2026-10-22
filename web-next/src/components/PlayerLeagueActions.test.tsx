import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { PlayerLeagueActions } from "./PlayerLeagueActions";
import { api } from "@/lib/api";

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      getMyRoster: vi.fn(),
      getGmTargets: vi.fn(),
      addGmTarget: vi.fn(),
      removeGmTarget: vi.fn(),
    },
  };
});

function renderActions(playerId: string) {
  return render(
    <PlayerLeagueActions leagueId="L1" leagueName="Dynasty Overlords" playerId={playerId} sourceSurface="player_quick_view" />,
  );
}

describe("PlayerLeagueActions", () => {
  beforeEach(() => {
    vi.mocked(api.getMyRoster).mockReset();
    vi.mocked(api.getGmTargets).mockReset();
    vi.mocked(api.addGmTarget).mockReset();
    vi.mocked(api.removeGmTarget).mockReset();
    vi.mocked(api.getMyRoster).mockResolvedValue({ ok: true, roster: { roster_id: 1, players: ["mine-1"] }, reason: "" });
    vi.mocked(api.getGmTargets).mockResolvedValue({ ok: true, targets: [] });
  });

  it("links Add to Trade to the analyzer with this player", async () => {
    renderActions("other-1");
    await act(async () => {});
    expect(screen.getByRole("link", { name: "Add to Trade" })).toHaveAttribute(
      "href",
      "/trade-analyzer/L1?name=Dynasty+Overlords&playerId=other-1",
    );
  });

  it("offers Find trades (not GM Targets) for a player on my roster", async () => {
    renderActions("mine-1");
    await act(async () => {});
    expect(screen.getByRole("link", { name: "Find trades" })).toHaveAttribute(
      "href",
      "/trade-finder/L1?name=Dynasty+Overlords&playerId=mine-1",
    );
    expect(screen.queryByRole("button", { name: /GM Targets/ })).toBeNull();
    expect(api.getGmTargets).not.toHaveBeenCalled();
  });

  it("offers Add to GM Targets (not Find trades) for someone else's player, and toggles it", async () => {
    vi.mocked(api.addGmTarget).mockResolvedValue({ ok: true, reason: "" });
    vi.mocked(api.removeGmTarget).mockResolvedValue({ ok: true, reason: "" });
    renderActions("other-1");
    await act(async () => {});
    expect(screen.queryByRole("link", { name: "Find trades" })).toBeNull();

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "☆ Add to GM Targets" }));
    });
    expect(api.addGmTarget).toHaveBeenCalledWith("L1", "other-1", "player_quick_view");
    const watching = screen.getByRole("button", { name: "★ Watching" });
    expect(watching).toHaveAttribute("aria-pressed", "true");

    await act(async () => {
      fireEvent.click(watching);
    });
    expect(api.removeGmTarget).toHaveBeenCalledWith("L1", "other-1");
    expect(screen.getByRole("button", { name: "☆ Add to GM Targets" })).toBeInTheDocument();
  });

  it("shows an already-watched player as Watching", async () => {
    vi.mocked(api.getGmTargets).mockResolvedValue({
      ok: true,
      targets: [{ player_id: "other-1", source_surface: "gm_targets", created_at: null, untouchable: false }],
    });
    renderActions("other-1");
    await act(async () => {});
    expect(screen.getByRole("button", { name: "★ Watching" })).toBeInTheDocument();
  });

  it("explains a full GM Targets list", async () => {
    vi.mocked(api.addGmTarget).mockResolvedValue({ ok: false, reason: "at_cap", cap: 25 });
    renderActions("other-1");
    await act(async () => {});
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: "☆ Add to GM Targets" }));
    });
    expect(screen.getByRole("status")).toHaveTextContent("GM Targets is full (25)");
    expect(screen.getByRole("button", { name: "☆ Add to GM Targets" })).toBeInTheDocument();
  });

  it("falls back to Add to Trade only when the roster can't be loaded", async () => {
    vi.mocked(api.getMyRoster).mockRejectedValue(new Error("offline"));
    renderActions("other-1");
    await act(async () => {});
    expect(screen.getByRole("link", { name: "Add to Trade" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Find trades" })).toBeNull();
    expect(screen.queryByRole("button", { name: /GM Targets/ })).toBeNull();
  });
});
