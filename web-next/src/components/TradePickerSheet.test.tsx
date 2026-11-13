import { fireEvent, render, screen, within } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { describe, expect, it, vi } from "vitest";

import { TradePickerSheet, TradeSideSummary } from "./TradePickerSheet";
import { itemKey, type SheetItem } from "@/lib/tradeSheetPicker";

function p(id: string, name: string, position: string, over: Partial<SheetItem> = {}): SheetItem {
  return { key: itemKey("player", id), kind: "player", id, label: name, position, team: "KC", age: 26, value: 1000, conditions: ["healthy"], photoId: null, ...over };
}
const ITEMS: SheetItem[] = [
  p("1", "Ann Runner", "RB"),
  p("2", "Bo Catcher", "WR", { conditions: ["injured"], injury: "Out" }),
  p("3", "Cy Rookie", "WR", { conditions: ["healthy", "rookie"], age: 21 }),
  { key: "pick:a", kind: "pick", id: "a", label: "2027 Round 1", position: null, team: null, age: null, value: 2000, conditions: [], round: 1, group: "2027 picks" },
];

function open(over: Partial<React.ComponentProps<typeof TradePickerSheet>> = {}) {
  const onApply = vi.fn();
  const onClose = vi.fn();
  const onInfo = vi.fn();
  render(<TradePickerSheet title="You send" subtitle="From your roster" tone="danger" items={ITEMS} initialSelected={[]} onApply={onApply} onClose={onClose} onInfo={onInfo} {...over} />);
  return { onApply, onClose, onInfo, dialog: screen.getByRole("dialog") };
}

describe("TradePickerSheet", () => {
  it("is a labelled modal dialog with focus moved into it", () => {
    const { dialog } = open();
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveAccessibleName("You send");
    expect(dialog).toHaveFocus();
  });

  it("toggles rows (aria-pressed), shows removable chips, and Add N hands back the whole selection", () => {
    const { dialog, onApply } = open();
    fireEvent.click(within(dialog).getByRole("button", { name: "Add Ann Runner" }));
    fireEvent.click(within(dialog).getByRole("button", { name: "Add Bo Catcher" }));
    expect(within(dialog).getByRole("button", { name: "Remove Ann Runner", pressed: true })).toBeInTheDocument();
    const chips = within(dialog).getByRole("list", { name: "Selected" });
    fireEvent.click(within(chips).getByRole("button", { name: "Remove Ann Runner" }));
    fireEvent.click(within(dialog).getByRole("button", { name: "Add 1 to trade" }));
    expect(onApply).toHaveBeenCalledWith(["player:2"]);
  });

  it("opens PQV from the info button only, never from the row", () => {
    const { dialog, onInfo } = open();
    fireEvent.click(within(dialog).getByRole("button", { name: "Add Ann Runner" }));
    expect(onInfo).not.toHaveBeenCalled();
    fireEvent.click(within(dialog).getByRole("button", { name: "Ann Runner player card" }));
    expect(onInfo).toHaveBeenCalledTimes(1);
    expect(within(dialog).getAllByRole("button", { name: "Remove Ann Runner" })).toHaveLength(2); // the row and its chip
  });

  it("filters through one Filters button; chips only count after Apply", () => {
    const { dialog } = open();
    fireEvent.click(within(dialog).getByRole("button", { name: /^Filters/ }));
    const panel = within(dialog).getByRole("group", { name: "Filters" });
    fireEvent.click(within(panel).getByRole("button", { name: "WR" }));
    fireEvent.click(within(panel).getByRole("button", { name: "Rookie" }));
    // Still unapplied: the list behind the panel is unchanged.
    expect(within(dialog).getAllByRole("listitem", { hidden: true }).filter((li) => li.classList.contains("tps-row"))).toHaveLength(3);
    fireEvent.click(within(panel).getByRole("button", { name: "Apply" }));
    expect(within(dialog).queryByRole("group", { name: "Filters" })).not.toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Filters (2)" })).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Add Cy Rookie" })).toBeInTheDocument();
    expect(within(dialog).queryByRole("button", { name: "Add Ann Runner" })).not.toBeInTheDocument();
    expect(within(dialog).queryByRole("button", { name: "Add Bo Catcher" })).not.toBeInTheDocument();
  });

  it("Escape closes the filter panel first, then the sheet", () => {
    const { dialog, onClose } = open();
    fireEvent.click(within(dialog).getByRole("button", { name: /^Filters/ }));
    fireEvent.keyDown(dialog, { key: "Escape" });
    expect(within(dialog).queryByRole("group", { name: "Filters" })).not.toBeInTheDocument();
    expect(onClose).not.toHaveBeenCalled();
    fireEvent.keyDown(dialog, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("traps Tab inside the dialog", () => {
    const { dialog } = open();
    const buttons = Array.from(dialog.querySelectorAll<HTMLElement>("button:not([disabled]), input"));
    const last = buttons[buttons.length - 1];
    last.focus();
    fireEvent.keyDown(last, { key: "Tab" });
    expect(dialog.contains(document.activeElement)).toBe(true);
    expect(document.activeElement).not.toBe(last);
    fireEvent.keyDown(document.activeElement as HTMLElement, { key: "Tab", shiftKey: true });
    expect(dialog.contains(document.activeElement)).toBe(true);
  });

  it("switches to Picks, grouped by season, and searches", () => {
    const { dialog } = open();
    fireEvent.click(within(dialog).getByRole("tab", { name: /Picks/ }));
    expect(within(dialog).getByText("2027 picks")).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Add 2027 Round 1" })).toBeInTheDocument();
    expect(within(dialog).queryByRole("button", { name: /^Filters/ })).not.toBeInTheDocument();
    fireEvent.change(within(dialog).getByRole("searchbox"), { target: { value: "zzz" } });
    expect(within(dialog).getByText("No matching picks.")).toBeInTheDocument();
  });

  it("stops at the max and says so", () => {
    const { dialog } = open({ max: 1 });
    fireEvent.click(within(dialog).getByRole("button", { name: "Add Ann Runner" }));
    expect(within(dialog).getByRole("button", { name: "Add Bo Catcher" })).toBeDisabled();
    expect(within(dialog).getByText(/max/)).toBeInTheDocument();
  });

  it("shows Done (not Add) when nothing changed and the close X closes without applying", () => {
    const { dialog, onClose, onApply } = open({ initialSelected: ["player:1"] });
    expect(within(dialog).getByRole("button", { name: "Done" })).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("button", { name: "Close You send" }));
    expect(onClose).toHaveBeenCalled();
    expect(onApply).not.toHaveBeenCalled();
  });

  it("animates the rise only when motion is allowed", () => {
    const css = readFileSync("src/app/globals.css", "utf8");
    expect(css).toMatch(/@media \(prefers-reduced-motion: reduce\) \{\s*\.tps-modal \{\s*animation: none;/);
  });
});

describe("TradeSideSummary", () => {
  it("opens from a tap on the whole header (not a tiny label), and chips remove", () => {
    const onOpen = vi.fn();
    const onRemove = vi.fn();
    render(<TradeSideSummary label="You send" tone="danger" items={[ITEMS[0], ITEMS[3]]} onOpen={onOpen} onRemove={onRemove} />);
    fireEvent.click(screen.getByRole("button", { name: /You send: 1 player, 1 pick/ }));
    expect(onOpen).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole("button", { name: "Remove Ann Runner" }));
    expect(onRemove).toHaveBeenCalledWith("player:1");
  });
  it("shows the hint when empty", () => {
    render(<TradeSideSummary label="You receive" tone="success" items={[]} onOpen={() => {}} onRemove={() => {}} hint="Add from any team" />);
    expect(screen.getByRole("button", { name: "You receive: add players or picks" })).toHaveTextContent("Add from any team");
  });
});
