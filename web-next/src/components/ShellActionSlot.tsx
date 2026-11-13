"use client";

import { useSyncExternalStore, type ReactNode } from "react";
import { createPortal } from "react-dom";

import { SHELL_ACTION_SLOT_ID } from "@/lib/shellNav";

const noopSubscribe = () => () => {};

/**
 * The page-aware action strip. A page renders `<ShellAction>...</ShellAction>`
 * and its content lands in the slot directly above the phone bottom bar
 * (AppShellBar renders the slot inside the sticky footer). Renders nothing
 * where the slot does not exist (desktop, the flag off, signed-out pages),
 * so a page can use it unconditionally and keep its in-page button for those.
 */
export function ShellAction({ children }: { children: ReactNode }) {
  const slot = useSyncExternalStore(
    noopSubscribe,
    () => document.getElementById(SHELL_ACTION_SLOT_ID),
    () => null,
  );
  return slot ? createPortal(children, slot) : null;
}
