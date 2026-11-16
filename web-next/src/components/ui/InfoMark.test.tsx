import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { InfoMark } from "./InfoMark";
import { experienceCopy } from "@/lib/experienceCopy";

let level: "beginner" | "advanced" = "beginner";
vi.mock("@/context/ExperienceLevelContext", () => ({
  useExperienceCopy: () => experienceCopy(level),
  useExperienceLevel: () => ({ level, setLevel: async () => {} }),
}));

describe("InfoMark", () => {
  beforeEach(() => {
    level = "beginner";
  });

  it("renders one inline '?' named after what it explains", () => {
    render(<InfoMark label="Roster Power" lines={["Plain sentence."]} />);
    const button = screen.getByRole("button", { name: "About Roster Power" });
    expect(button.textContent).toBe("?");
    expect(button).toHaveAttribute("aria-haspopup", "dialog");
  });

  it("opens a sheet with lines, registry metrics and glossary terms behind the one mark", () => {
    render(<InfoMark label="Team Snapshot" lines={["A plain line."]} metrics={["power_rank"]} glossary={["averageAge"]} />);
    expect(screen.getAllByRole("button", { name: /^About / })).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "About Team Snapshot" }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByText("A plain line.")).toBeInTheDocument();
    expect(screen.getByText("Average Age")).toBeInTheDocument();
  });

  it("renders free-form children in the sheet", () => {
    render(<InfoMark label="this page">{<p>Child body</p>}</InfoMark>);
    fireEvent.click(screen.getByRole("button", { name: "About this page" }));
    expect(screen.getByText("Child body")).toBeInTheDocument();
  });

  it("beginnerOnly marks render for beginners and are hidden for advanced accounts", () => {
    const { unmount } = render(<InfoMark label="the plan" lines={["Help."]} beginnerOnly />);
    expect(screen.getByRole("button", { name: "About the plan" })).toBeInTheDocument();
    unmount();
    level = "advanced";
    render(<InfoMark label="the plan" lines={["Help."]} beginnerOnly />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("returns null without content", () => {
    const { container } = render(<InfoMark label="nothing" lines={[null, undefined]} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("requires a label at the type level", () => {
    // @ts-expect-error label is required: a bare '?' has no referent
    const el = <InfoMark lines={["x"]} />;
    expect(el).toBeTruthy();
  });
});
