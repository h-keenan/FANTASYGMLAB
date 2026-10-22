import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ManagerProfileSheet } from "./ManagerProfileSheet";

vi.mock("@/lib/api", () => ({
  api: { getManagerTendencyDetail: () => new Promise(() => {}) },
}));

describe("ManagerProfileSheet header", () => {
  it("shows team name, manager name and avatar", () => {
    const { container } = render(
      <ManagerProfileSheet leagueId="1" rosterId={3} teamName="Big Dogs" ownerName="Zach K" avatarUrl="https://sleepercdn.com/avatars/thumbs/abc" onClose={() => {}} />,
    );
    expect(screen.getByText("Big Dogs")).toBeTruthy();
    expect(screen.getByText("Zach K")).toBeTruthy();
    expect(container.querySelector("img")?.getAttribute("src")).toContain("abc");
  });

  it("falls back to initials without an avatar", () => {
    render(<ManagerProfileSheet leagueId="1" rosterId={3} teamName="Big Dogs" ownerName="Zach K" onClose={() => {}} />);
    expect(screen.getByText("ZK")).toBeTruthy();
  });
});
