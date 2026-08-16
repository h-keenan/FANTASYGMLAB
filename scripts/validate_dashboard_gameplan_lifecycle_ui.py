"""Timed Dashboard Game Plan richness: first paint plus automatic later paints.

Previous geometry validation captured too early. This waits >=20s and re-checks
that Top Priority / Watch / Waiver stay rich after deferred remounts.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

WIDTHS = (320, 390, 430, 768, 1440)
SNAPSHOT_SECONDS = (0, 5, 10, 15, 20)


def _snapshot(page) -> dict:
    return page.evaluate(
        """() => {
          const text = document.body ? (document.body.innerText || '') : '';
          const trade = document.querySelector('[data-gp-trade-visual]');
          const watch = document.querySelector('[data-gp-watch]');
          const waiver = [...document.querySelectorAll('.dg-game-plan-card')]
            .find(el => /waiver/i.test(el.innerText || ''));
          const box = (el) => {
            if (!el) return null;
            const r = el.getBoundingClientRect();
            return {top: r.top, bottom: r.bottom, left: r.left, right: r.right, height: r.height, width: r.width};
          };
          const overlaps = (a, b) => {
            if (!a || !b) return false;
            return !(a.bottom <= b.top + 1 || b.bottom <= a.top + 1);
          };
          const lede = document.querySelector('.dg-game-plan-lede, [class*="_lede"] [data-testid="stCaptionContainer"]');
          const utility = document.querySelector('.dg-game-plan-utility, [class*="_utility"] [data-testid="stCaptionContainer"]');
          const refreshBtn = [...document.querySelectorAll('button')].find(el => {
            const r = el.getBoundingClientRect();
            const label = (el.innerText || '').replace(/\\s+/g, ' ').trim().toLowerCase();
            return label === 'refresh' && r.width > 1 && r.height > 1;
          });
          const avatars = [...document.querySelectorAll('.dg-player-headshot')].map(el => {
            const img = el.querySelector('img.dg-player-headshot-image');
            const fallback = el.querySelector('.dg-player-headshot-fallback');
            const cs = fallback ? getComputedStyle(fallback) : null;
            return {
              hasImg: Boolean(img),
              imgDisplay: img ? getComputedStyle(img).display : '',
              fallbackOpacity: cs ? cs.opacity : '',
              fallbackVisibility: cs ? cs.visibility : '',
            };
          });
          return {
            text,
            hasYouGive: /you give/i.test(text),
            hasYouGet: /you get/i.test(text),
            hasTracy: /tyrone tracy/i.test(text),
            hasBryant: /pat bryant/i.test(text),
            hasValueEdge: /value edge/i.test(text),
            hasPipeWatch: /skattebo \\(rb\\).*\\|.*sadiq/i.test(text),
            hasSkattebo: /cam skattebo/i.test(text),
            hasWilson: /emanuel wilson|brashard smith/i.test(text),
            tradeHtml: trade ? trade.innerHTML : '',
            watchHtml: watch ? watch.innerHTML : '',
            waiverHtml: waiver ? waiver.innerHTML : '',
            overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
            ledeFont: lede ? getComputedStyle(lede).fontSize : '',
            utilityFont: utility ? getComputedStyle(utility).fontSize : '',
            headerOverlap: overlaps(box(lede), box(utility))
              || overlaps(box(utility), box(refreshBtn))
              || overlaps(box(lede), box(refreshBtn)),
            avatars,
          };
        }"""
    )


def _assert_rich(snapshot: dict, *, width: int, elapsed: int) -> list[str]:
    failures: list[str] = []
    label = f"{width}@{elapsed}s"
    if not snapshot.get("hasYouGive") or not snapshot.get("hasYouGet"):
        failures.append(f"{label}: Top Priority lost YOU GIVE / YOU GET")
    if not snapshot.get("hasTracy") or not snapshot.get("hasBryant"):
        failures.append(f"{label}: Top Priority lost player identities")
    if not snapshot.get("hasValueEdge"):
        failures.append(f"{label}: Top Priority lost value edge")
    if snapshot.get("hasPipeWatch"):
        failures.append(f"{label}: Watch collapsed to pipe-delimited legacy text")
    if not snapshot.get("hasSkattebo"):
        failures.append(f"{label}: Watch lost player identity")
    if not snapshot.get("hasWilson"):
        failures.append(f"{label}: Waiver lost player identity")
    trade_html = str(snapshot.get("tradeHtml") or "")
    watch_html = str(snapshot.get("watchHtml") or snapshot.get("waiverHtml") or "")
    combined = f"{trade_html} {watch_html} {snapshot.get('waiverHtml') or ''}"
    if "dg-compact-asset-avatar" not in combined and "dg-player-headshot" not in combined:
        failures.append(f"{label}: portraits missing from Game Plan")
    if snapshot.get("overflow"):
        failures.append(f"{label}: horizontal overflow")
    if snapshot.get("headerOverlap"):
        failures.append(f"{label}: subtitle/timestamp/Refresh overlap")
    for avatar in snapshot.get("avatars") or ():
        if avatar.get("hasImg") and str(avatar.get("fallbackOpacity")) not in {"0", "0.0"}:
            if str(avatar.get("fallbackVisibility")).casefold() != "hidden":
                failures.append(f"{label}: initials visible under player photo")
                break
    return failures


def main() -> int:
    from playwright.sync_api import sync_playwright

    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8510")
    parser.add_argument("--output", default="artifacts/dashboard-gameplan-lifecycle")
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    report: dict = {"widths": list(WIDTHS), "snapshots": {}}
    failures: list[str] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        try:
            for width in WIDTHS:
                page = browser.new_page(
                    viewport={"width": width, "height": 844},
                    device_scale_factor=1,
                )
                try:
                    page.goto(
                        f"{args.base_url}/?surface=dashboard",
                        wait_until="networkidle",
                        timeout=60_000,
                    )
                    page.get_by_text("Today's Game Plan", exact=False).first.wait_for(
                        state="attached", timeout=60_000
                    )
                    started = time.monotonic()
                    report["snapshots"][str(width)] = {}
                    for mark in SNAPSHOT_SECONDS:
                        remaining = mark - (time.monotonic() - started)
                        if remaining > 0:
                            page.wait_for_timeout(int(remaining * 1000))
                        snap = _snapshot(page)
                        page.screenshot(
                            path=str(output / f"dashboard-{width}-t{mark}.png"),
                            full_page=True,
                        )
                        report["snapshots"][str(width)][f"t{mark}"] = {
                            "hasYouGive": snap.get("hasYouGive"),
                            "hasYouGet": snap.get("hasYouGet"),
                            "hasTracy": snap.get("hasTracy"),
                            "hasPipeWatch": snap.get("hasPipeWatch"),
                            "headerOverlap": snap.get("headerOverlap"),
                            "ledeFont": snap.get("ledeFont"),
                            "utilityFont": snap.get("utilityFont"),
                            "avatarCount": len(snap.get("avatars") or ()),
                        }
                        failures.extend(_assert_rich(snap, width=width, elapsed=mark))
                finally:
                    page.close()
        finally:
            browser.close()
    report["failures"] = failures
    (output / "validation-report.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    if failures:
        raise AssertionError("; ".join(failures))
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
