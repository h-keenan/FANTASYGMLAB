import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { GlossaryNote } from "./GlossaryNote";
import { GLOSSARY, SETTINGS_GLOSSARY_TERMS } from "@/lib/glossary";

describe("GlossaryNote", () => {
  it("is collapsed until tapped, then shows each shared definition", () => {
    render(<GlossaryNote terms={["powerRank", "benchStrength"]} />);
    expect(screen.queryByText(GLOSSARY.powerRank.definition)).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /what do these mean/i }));
    expect(screen.getByText(GLOSSARY.powerRank.definition)).toBeInTheDocument();
    expect(screen.getByText(GLOSSARY.benchStrength.definition)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /what do these mean/i })).toHaveAttribute("aria-expanded", "true");
  });

  it("explains the dynasty jargon (PQV, picks, superflex, TEP, FAAB, taxi) in plain language", () => {
    render(<GlossaryNote terms={SETTINGS_GLOSSARY_TERMS} />);
    fireEvent.click(screen.getByRole("button", { name: /what do these mean/i }));
    for (const key of ["pqv", "picks", "superflex", "tep", "faab", "taxi"] as const) {
      expect(screen.getByText(GLOSSARY[key].definition)).toBeInTheDocument();
    }
  });
});
