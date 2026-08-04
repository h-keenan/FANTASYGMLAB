# Founder QA Punch List

This is the durable collection point for non-blocking Founder Beta polish. Items stay here until a scheduled Founder Polish Sprint can resolve a coherent batch; they do not trigger one-off PRs.

## Intake rules

Record the page/state, viewport, evidence, user impact, and likely owner. Do not mix football correctness, security, data integrity, or production crashes into this list—those remain immediate defects.

## Open observations

| ID | Surface / state | Observation | Impact | Evidence | Suggested batch |
|---|---|---|---|---|---|
| FQA-001 | Authenticated workspace, mobile | The league switch control is functionally adjacent to the command header but is a separate native Streamlit control. | Minor context/action separation. | PR #99 mobile validation | Shell polish |
| FQA-002 | Comparative dialogs, 320px | Leaderboard rows are clear, but long team/manager combinations can make the first viewport dense. | Extra scrolling in large leagues. | PR #99 screenshots | Modal density |
| FQA-003 | Dashboard, 320px | Supporting sentences under Immediate Action and Your Next Move remain close in visual weight. | Slower scan for first-time users. | PR #99 screenshots | Typography hierarchy |
| FQA-004 | Trade Hub fixture footer | Synthetic-data disclaimer sits close to the first recommendation card in the validation harness. | Visual noise in fixture review only. | PR #99 screenshots | Harness polish |
| FQA-005 | Harness `?surface=` routing | Browser back/forward does not reliably restore workspace surface the way GM Orb navigation does. | Mild history confusion in fixture/review only. | LC0 stress (`docs/founder-beta-lc0.md`) | Navigation polish |
| FQA-006 | Local AppTest / perf audits | Running production AppTest can refresh tracked `data/players.db` beyond the committed 988-row fixture. | Local suite noise if fixtures are not restored before commit. | LC0 (`docs/founder-beta-lc0.md`) | Dev hygiene |

## Completed

Move resolved items here with PR and screenshot evidence. Preserve IDs for history.
