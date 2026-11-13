import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { SHELL_ACTION_SLOT_ID } from "@/lib/shellNav";

import { ShellAction } from "./ShellActionSlot";

describe("ShellAction", () => {
  it("renders nothing when there is no slot (desktop, flag off)", () => {
    render(<ShellAction><button>Do it</button></ShellAction>);
    expect(screen.queryByRole("button", { name: "Do it" })).toBeNull();
  });
  it("lands in the slot above the tab bar when one exists", () => {
    const slot = document.createElement("div");
    slot.id = SHELL_ACTION_SLOT_ID;
    document.body.appendChild(slot);
    render(<ShellAction><button>Do it</button></ShellAction>);
    expect(slot.contains(screen.getByRole("button", { name: "Do it" }))).toBe(true);
    slot.remove();
  });
});
