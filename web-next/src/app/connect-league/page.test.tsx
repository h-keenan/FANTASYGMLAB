import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ConnectLeaguePage from "./page";
import { useAuth } from "@/context/AuthContext";
import { readProtectedReturnPath } from "@/lib/protectedRouteReturn";
import { signedIn } from "@/lib/pageFetchTestKit";

vi.mock("@/context/AuthContext", () => ({ useAuth: vi.fn() }));

const router = { replace: vi.fn(), push: vi.fn() };
vi.mock("next/navigation", () => ({ useRouter: () => router }));

vi.mock("@/components/SleeperImportForm", () => ({
  SleeperImportForm: () => <div>SleeperImportForm</div>,
}));
vi.mock("@/components/FreeLeagueLimitNote", () => ({
  FreeLeagueLimitNote: () => null,
}));
vi.mock("@/components/SampleLeagueBanner", () => ({
  SampleLeagueButton: () => null,
}));

beforeEach(() => {
  vi.clearAllMocks();
  window.localStorage.clear();
  window.history.pushState({}, "", "/connect-league");
});

// P0 UX audit, 2026-10-27: a signed-out visitor used to be dropped on "/"
// with no way back to this exact page once they signed in.
describe("ConnectLeaguePage signed-out redirect", () => {
  it("stores the current path before bouncing to / so sign-in can return here", async () => {
    vi.mocked(useAuth).mockReturnValue({ session: null, loading: false } as unknown as ReturnType<typeof useAuth>);
    render(<ConnectLeaguePage />);

    await waitFor(() => expect(router.replace).toHaveBeenCalledWith("/"));
    expect(readProtectedReturnPath(window.localStorage)).toBe("/connect-league");
  });

  it("does not redirect or store anything while auth is still resolving", () => {
    vi.mocked(useAuth).mockReturnValue({ session: null, loading: true } as unknown as ReturnType<typeof useAuth>);
    render(<ConnectLeaguePage />);

    expect(router.replace).not.toHaveBeenCalled();
    expect(readProtectedReturnPath(window.localStorage)).toBeNull();
  });

  it("renders the real add-a-league form for a signed-in visitor, without storing a return path", async () => {
    vi.mocked(useAuth).mockReturnValue(signedIn as unknown as ReturnType<typeof useAuth>);
    render(<ConnectLeaguePage />);

    expect(await screen.findByText("SleeperImportForm")).toBeInTheDocument();
    expect(router.replace).not.toHaveBeenCalled();
    expect(readProtectedReturnPath(window.localStorage)).toBeNull();
  });
});
