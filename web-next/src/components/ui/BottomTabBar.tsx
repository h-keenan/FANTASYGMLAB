"use client";

import Link from "next/link";

import { TabGlyph } from "@/components/TabGlyph";
import { activeBottomTab, bottomTabAriaLabel, bottomTabBadgeText, type BottomTab } from "@/lib/bottomNav";

import "./ui.css";

/**
 * Phone bottom tab bar. Icon over label, a count badge, 52px tall targets,
 * glass blur and the home-indicator inset. Meant to live inside a
 * `.bottom-stack` (sticky, in flow), never position:fixed. Hidden from 768px
 * up (the desktop layouts have their own tabs / sidebar).
 *
 * a11y: a labelled <nav> holding a list of buttons (or links when a tab has
 * an `href`); the lit tab carries aria-current="page" and a badge is read as
 * "Trades, 2 new". Mobile twin: mobile/src/components/BottomTabBar.tsx.
 */
export function BottomTabBar({
  tabs,
  active,
  onSelect,
  ariaLabel,
  testId = "bottom-tab-bar",
}: {
  tabs: BottomTab[];
  active: string;
  onSelect?: (key: string) => void;
  ariaLabel: string;
  testId?: string;
}) {
  const current = activeBottomTab(tabs, active);
  return (
    <nav className="bottom-tab-bar" aria-label={ariaLabel} data-testid={testId}>
      <ul>
        {tabs.map((tab) => {
          const badge = bottomTabBadgeText(tab.badge);
          const body = (
            <>
              <span className="bottom-tab-icon" aria-hidden="true">
                <TabGlyph name={tab.glyph} size={22} />
              </span>
              <span className="bottom-tab-label">{tab.label}</span>
              {badge ? (
                <span className="bottom-tab-badge" aria-hidden="true" data-testid={`bottom-tab-badge-${tab.key}`}>
                  {badge}
                </span>
              ) : null}
            </>
          );
          const common = {
            className: "bottom-tab",
            "aria-current": tab.key === current ? ("page" as const) : undefined,
            "aria-label": bottomTabAriaLabel(tab),
            "data-tab": tab.key,
          };
          return (
            <li key={tab.key}>
              {tab.href ? (
                <Link href={tab.href} {...common} onClick={() => onSelect?.(tab.key)}>
                  {body}
                </Link>
              ) : (
                <button type="button" {...common} onClick={() => onSelect?.(tab.key)}>
                  {body}
                </button>
              )}
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
