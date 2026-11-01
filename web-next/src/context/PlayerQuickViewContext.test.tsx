import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

let routeParams: { leagueId?: string } | null = null;
vi.mock("next/navigation", () => ({
  useParams: () => routeParams,
  usePathname: () => "/news/L9",
}));

const shown = vi.fn();
vi.mock("@/components/PlayerQuickView", () => ({
  PlayerQuickView: ({ identity }: { identity: { leagueId?: string; leagueName?: string } }) => {
    shown(identity.leagueId, identity.leagueName);
    return <div>quick view open</div>;
  },
}));
vi.mock("@/lib/analytics", () => ({ trackFeatureUse: vi.fn() }));

import { PlayerQuickViewProvider, usePlayerQuickView } from "./PlayerQuickViewContext";

function Opener({ leagueId }: { leagueId?: string }) {
  const { openPlayer } = usePlayerQuickView();
  return <button onClick={() => openPlayer({ player_id: "p1", leagueId })}>open</button>;
}

async function open(leagueId?: string) {
  render(
    <PlayerQuickViewProvider>
      <Opener leagueId={leagueId} />
    </PlayerQuickViewProvider>,
  );
  fireEvent.click(screen.getByText("open"));
  await act(async () => {});
}

describe("PlayerQuickViewProvider league fallback", () => {
  beforeEach(() => shown.mockClear());

  it("uses the route's league when the caller passed none", async () => {
    routeParams = { leagueId: "L9" };
    window.history.pushState({}, "", "/news/L9?name=My+League");
    await open();
    expect(shown).toHaveBeenCalledWith("L9", "My League");
  });

  it("keeps an explicit league and stays league-less off league routes", async () => {
    routeParams = { leagueId: "L9" };
    await open("L1");
    expect(shown).toHaveBeenCalledWith("L1", undefined);
    shown.mockClear();
    document.body.innerHTML = "";
    routeParams = null;
    await open();
    expect(shown).toHaveBeenCalledWith(undefined, undefined);
  });
});
