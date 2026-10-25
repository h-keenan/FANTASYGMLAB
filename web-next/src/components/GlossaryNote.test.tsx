import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { GlossaryNote } from "./GlossaryNote";
import { GLOSSARY } from "@/lib/glossary";

describe("GlossaryNote", () => {
  it("is collapsed until tapped, then shows each shared definition", () => {
    render(<GlossaryNote terms={["powerRank", "benchStrength"]} />);
    expect(screen.queryByText(GLOSSARY.powerRank.definition)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /what do these mean/i }));
    expect(screen.getByText(GLOSSARY.powerRank.definition)).toBeInTheDocument();
    expect(screen.getByText(GLOSSARY.benchStrength.definition)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /what do these mean/i })).toHaveAttribute("aria-expanded", "true");
  });
});
