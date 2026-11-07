import { screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import WaiversPage from "./page";
import { useAuth } from "@/context/AuthContext";
import { api, type WaiversResponse } from "@/lib/api";
import { mockLeagueType, renderWithLens, signedIn } from "@/lib/pageFetchTestKit";

vi.mock("@/context/AuthContext", () => ({ useAuth: vi.fn() }));
vi.mock("@/lib/analytics", () => ({ trackFeatureUse: vi.fn() }));

const router = { replace: vi.fn(), push: vi.fn() };
vi.mock("next/navigation", () => ({
  useRouter: () => router,
  useParams: () => ({ leagueId: "league-1" }),
  useSearchParams: () => new URLSearchParams("name=My League"),
}));

vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, api: { ...actual.api, getLeagueWaivers: vi.fn(), getLeague: vi.fn() } };
});

vi.mock("@/components/WaiversContent", () => ({
  WaiversContent: () => <div data-testid="waivers" />,
}));

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
  vi.mocked(useAuth).mockReturnValue(signedIn);
});

describe("WaiversPage fetch order", () => {
  it("fetches a redraft league once, with the redraft lens (no Dynasty-then-redraft double fetch)", async () => {
    mockLeagueType(0);
    vi.mocked(api.getLeagueWaivers).mockResolvedValue({ ok: true } as WaiversResponse);

    renderWithLens(<WaiversPage />);

    expect(await screen.findByTestId("waivers")).toBeInTheDocument();
    await waitFor(() => expect(api.getLeagueWaivers).toHaveBeenCalledTimes(1));
    expect(api.getLeagueWaivers).toHaveBeenCalledWith("league-1", "Non-Dynasty");
  });
});
