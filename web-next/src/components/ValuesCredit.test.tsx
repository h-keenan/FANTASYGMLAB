import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import MethodologyPage from "@/app/methodology/page";
import { ValuesCredit } from "@/components/ValuesCredit";

describe("ValuesCredit", () => {
  it("credits FantasyCalc with a link to fantasycalc.com", () => {
    render(<ValuesCredit />);
    expect(screen.getByTestId("values-credit")).toHaveTextContent("Values informed by FantasyCalc");
    const link = screen.getByRole("link", { name: "FantasyCalc" });
    expect(link).toHaveAttribute("href", "https://fantasycalc.com");
    expect(link).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("appears on the public methodology page", () => {
    render(<MethodologyPage />);
    expect(screen.getByRole("link", { name: "FantasyCalc" })).toHaveAttribute("href", "https://fantasycalc.com");
  });
});
