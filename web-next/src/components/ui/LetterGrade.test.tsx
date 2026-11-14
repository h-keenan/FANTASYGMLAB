import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { GradeBar, GradeLegendButton, LetterGrade } from "@/components/ui/LetterGrade";

describe("LetterGrade", () => {
  it("renders the letter with an accessible name and no numeric rating", () => {
    render(<LetterGrade grade={{ grade: "A-" }} />);
    const el = screen.getByTestId("letter-grade");
    expect(el).toHaveTextContent("A-");
    expect(el).toHaveAttribute("aria-label", "Grade A minus, very good starter");
    expect(el.textContent).not.toMatch(/\d/);
  });
  it("tints by tone with existing tokens only", () => {
    const { rerender } = render(<LetterGrade grade={{ grade: "A" }} />);
    expect(screen.getByTestId("letter-grade").style.boxShadow).toContain("var(--color-success)");
    rerender(<LetterGrade grade={{ grade: "B" }} />);
    expect(screen.getByTestId("letter-grade").style.boxShadow).toContain("var(--color-accent)");
    rerender(<LetterGrade grade={{ grade: "C" }} />);
    expect(screen.getByTestId("letter-grade").style.boxShadow).toContain("var(--color-action)");
    rerender(<LetterGrade grade={{ grade: "D" }} />);
    expect(screen.getByTestId("letter-grade").style.boxShadow).toContain("var(--color-warning)");
    rerender(<LetterGrade grade={{ grade: "F" }} />);
    expect(screen.getByTestId("letter-grade").style.boxShadow).toContain("var(--color-danger)");
  });
  it("shows a ? and the range for an unsure grade; reserves its footprint with no grade", () => {
    const { rerender } = render(<LetterGrade grade={{ grade: "B", grade_uncertain: true, grade_range: ["B-", "A-"] }} size="lg" />);
    expect(screen.getByTestId("letter-grade")).toHaveTextContent("B?");
    expect(screen.getByTestId("letter-grade")).toHaveTextContent("B-/A-");
    rerender(<LetterGrade grade={null} />);
    expect(screen.queryByTestId("letter-grade")).toBeNull();
    expect(screen.getByTestId("letter-grade-empty")).toBeInTheDocument();
  });
});

describe("GradeBar and the legend", () => {
  it("labels an attribute with its grade", () => {
    render(<GradeBar attribute={{ key: "volume", label: "Targets", grade: "B+" }} />);
    expect(screen.getByTestId("grade-bar")).toHaveAttribute("aria-label", expect.stringContaining("Targets: Grade B plus"));
  });
  it("opens a legend listing all twelve grades", () => {
    render(<GradeLegendButton />);
    fireEvent.click(screen.getByRole("button", { name: "What the grades mean" }));
    expect(screen.getAllByTestId("legend-grade")).toHaveLength(12);
  });
});
