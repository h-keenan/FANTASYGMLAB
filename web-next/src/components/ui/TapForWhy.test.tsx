import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { WHY_REGISTRY } from "@/lib/tapForWhyContent";

import { TapForWhy, TapForWhyOff } from "./TapForWhy";

vi.mock("@/lib/analytics", () => ({ trackUse: vi.fn() }));

describe("TapForWhy", () => {
  it("renders the child unchanged inside a labelled button with dialog semantics", () => {
    render(
      <TapForWhy metric="value" spoken="Value 82">
        <span>82</span>
      </TapForWhy>,
    );
    const button = screen.getByRole("button", { name: "Why: Value 82" });
    expect(button).toHaveAttribute("aria-haspopup", "dialog");
    expect(button).toHaveTextContent("82");
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("opens a sheet with the registry copy, a chart slot and a learn-more link, and closes on Escape", () => {
    render(
      <TapForWhy metric="value" spoken="Value 82" chart={<div>mini chart</div>}>
        <span>82</span>
      </TapForWhy>,
    );
    const trigger = screen.getByRole("button", { name: "Why: Value 82" });
    trigger.focus();
    fireEvent.click(trigger);
    const dialog = screen.getByRole("dialog", { name: WHY_REGISTRY.value.title });
    expect(dialog).toHaveTextContent(WHY_REGISTRY.value.sentences[0]);
    expect(screen.getByText("mini chart")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /How values are built/ })).toHaveAttribute("href", "/methodology");
    fireEvent.keyDown(dialog, { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(trigger).toHaveFocus();
  });

  it("appends instance-specific sentences after the registry copy", () => {
    render(
      <TapForWhy metric="usage_trend" extra={["Targets are up 12% over four games."]}>
        <span>up</span>
      </TapForWhy>,
    );
    fireEvent.click(screen.getByRole("button"));
    expect(screen.getByText("Targets are up 12% over four games.")).toBeInTheDocument();
  });

  it("has 1 to 3 plain sentences for every registered metric", () => {
    for (const entry of Object.values(WHY_REGISTRY)) {
      expect(entry.sentences.length).toBeGreaterThanOrEqual(1);
      expect(entry.sentences.length).toBeLessThanOrEqual(3);
      expect(entry.title.length).toBeGreaterThan(0);
    }
  });

  it("TapForWhyOff (the sim trade window) leaves the pill as plain text: nothing to tap, no sheet", () => {
    render(
      <TapForWhyOff>
        <TapForWhy metric="value" spoken="Value 82">
          <span>82</span>
        </TapForWhy>
      </TapForWhyOff>,
    );
    expect(screen.getByText("82")).toBeInTheDocument();
    expect(screen.queryByRole("button")).toBeNull();
  });
});
