import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";

import { PillOrb } from "@/components/ui/PillOrb";
import { ORB_COACHMARK_SEEN_KEY, ORB_COACHMARK_TEXT } from "@/lib/orbCoachmark";

describe("PillOrb menu affordance (audit F1)", () => {
  beforeEach(() => window.localStorage.clear());

  it("always carries the persistent menu cue", () => {
    render(<PillOrb label="Menu" onClick={() => {}} />);
    expect(screen.getByTestId("pill-orb-cue")).toBeInTheDocument();
  });

  it("shows the coachmark once, then never again after the first tap", () => {
    const { unmount } = render(<PillOrb label="Menu" coachmark onClick={() => {}} />);
    expect(screen.getByTestId("pill-orb-coachmark")).toHaveTextContent(ORB_COACHMARK_TEXT);
    fireEvent.click(screen.getByTestId("pill-orb"));
    expect(screen.queryByTestId("pill-orb-coachmark")).toBeNull();
    expect(window.localStorage.getItem(ORB_COACHMARK_SEEN_KEY)).toBe("1");
    unmount();
    render(<PillOrb label="Menu" coachmark onClick={() => {}} />);
    expect(screen.queryByTestId("pill-orb-coachmark")).toBeNull();
  });

  it("shows no coachmark where it is not requested", () => {
    render(<PillOrb label="Menu" onClick={() => {}} />);
    expect(screen.queryByTestId("pill-orb-coachmark")).toBeNull();
  });
});
