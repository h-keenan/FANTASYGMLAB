import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DesktopSidebar } from "./DesktopSidebar";
import { api } from "@/lib/api";
import { useAuth } from "@/context/AuthContext";

vi.mock("@/context/AuthContext", () => ({ useAuth: vi.fn() }));
vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard/L1",
  useParams: () => ({ leagueId: "L1" }),
  useSearchParams: () => new URLSearchParams("name=My%20League"),
}));
vi.mock("@/lib/api", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api")>("@/lib/api");
  return { ...actual, api: { ...actual.api, getCommissionerStatus: vi.fn() } };
});

describe("Commissioner nav entry", () => {
  beforeEach(() => vi.mocked(useAuth).mockReturnValue({ session: { user: { id: "u", app_metadata: {} } }, loading: false } as never));

  it("appears only after the server confirms the user is the commissioner", async () => {
    vi.mocked(api.getCommissionerStatus).mockResolvedValue({ ok: true, is_commissioner: true, reason: "" });
    render(<DesktopSidebar />);
    const link = await screen.findByText("Commissioner");
    expect(link.closest("a")).toHaveAttribute("href", "/commissioner/L1?name=My%20League");
  });
});
