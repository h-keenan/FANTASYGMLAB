import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DesktopSidebar } from "./DesktopSidebar";
import { useAuth } from "@/context/AuthContext";

vi.mock("@/context/AuthContext", () => ({ useAuth: vi.fn() }));
vi.mock("next/navigation", () => ({
  usePathname: () => "/dashboard/L1",
  useParams: () => ({ leagueId: "L1" }),
  useSearchParams: () => new URLSearchParams("name=My%20League"),
}));

describe("Commissioner nav entry", () => {
  it("is listed under GM Tools for a league (Pro gating happens on the page)", () => {
    vi.mocked(useAuth).mockReturnValue({ session: { user: { id: "u", app_metadata: {} } }, loading: false } as never);
    render(<DesktopSidebar />);
    expect(screen.getByText("Commissioner").closest("a")).toHaveAttribute("href", "/commissioner/L1?name=My%20League");
  });
});
