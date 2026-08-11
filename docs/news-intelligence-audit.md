# News → football event → roster-aware alerts audit

Branch: `cursor/news-event-roster-alerts-71e1`  
Base / rollback SHA: `e544cf79d3b1d2cdaca48acdfa750b1e264306ae` (main @ #253)  
Do **not** reopen valuation calibration (#252/#253 superseded work).

## Verdict

**NEWS INTELLIGENCE NEEDS MORE WORK**

Trustworthy for: article→event classification, roster-aware alert severity,
anti-spam dedupe/escalation, cached-news Dashboard tiles, and the valuation
firewall (articles cannot write score columns).

Not yet fully trustworthy for: live corroboration against every structured
football owner beyond Sleeper injury/status, rich depth-chart mutation from
articles (intentionally blocked), and package-cache hit paths that skip
rebuilding Dashboard tiles (alerts refresh on package miss / next build).

---

## Canonical owners

| Concern | Owner |
|---|---|
| RSS / Google fetch + disk cache | `modules/news.py` |
| Sleeper synthetic roster cards | `modules/my_news.build_sleeper_roster_updates` |
| Coarse signal taxonomy / confidence / event_identity | `modules/news_signal.py` |
| Fine-grained football events + roster alerts | `modules/news_intelligence.py` |
| Alert delivery | Dashboard tiles → `notification_center.publish_activity_inventory` |
| Structured injury/status valuation inputs | Sleeper fields → `rankings.injury_level` / `risk_multiplier` |
| Role/depth notes | Structured Sleeper diffs only (`populate_structured_role_notes_from_sleeper`) |

## Exact flow

```
RSS/Google/Sleeper
  → fetch / disk TTL cache (Dashboard alerts: load_cached_news_pool only)
  → normalize + entity match (news / my_news)
  → news_signal.enrich_news_item (ranking + football_event_type)
  → news_intelligence.football_event_from_article
  → roster relationship (MY_STARTER / BENCH / TAXI / IR / FA / OPPONENT)
  → severity + league-context relevance (alert only)
  → dedupe / escalation session state
  → Dashboard "News Alert" tiles → Notification Center
  → structured Sleeper status change (separate path)
  → rankings risk/availability multipliers (valuation)
```

**Invariant:** RAW NEWS ≠ PLAYER VALUE. Articles never write `score`,
`base_score`, `dynasty_score`, `value_score`, `league_*`, `strategy_score`,
`news_factor`, or injury multipliers.

## Event taxonomy

`INJURY`, `INJURY_SEVERITY_UPDATE`, `IR_PUP_NFI`, `RETURN_TO_PRACTICE`,
`RETURN_TO_PLAY`, `INACTIVE`, `ACTIVE`, `STARTER_CHANGE`, `DEPTH_CHART_CHANGE`,
`ROLE_INCREASE`, `ROLE_DECREASE`, `POSITION_BATTLE`, `TRADE`, `SIGNING`,
`RELEASE`, `SUSPENSION`, `RETIREMENT`, `OTHER`

Speculation (`could start`, `expected to start`, competing language) →
`POSITION_BATTLE` / role signals with `confirmed_starter=False`.
Official named-starter language → `STARTER_CHANGE` with `confirmed_starter=True`.

## Confidence / corroboration

Evidence hierarchy (small by design):

- A `A_structured_state` — Sleeper status/injury already matches
- B `B_confirmed_report` — official / strong reporter confirmation
- C `C_beat_signal` — coach / beat observation
- D `D_speculation` — opinion / hedge language

Independent corroboration counts distinct sources per `event_identity`.
Syndicated copies share identity (from #250) and do **not** inflate confidence.

## Roster-aware severity (examples)

| Event | Relationship | Typical severity |
|---|---|---|
| Ruled OUT | MY_STARTER | CRITICAL |
| IR | MY_STARTER | CRITICAL |
| Named starter | FREE_AGENT | HIGH (waiver) |
| Position battle | MY_STARTER | MEDIUM + uncertainty copy |
| Ruled OUT | OPPONENT | ≤ MEDIUM |
| Speculative FA battle | FREE_AGENT | LOW / suppressed |

## League-context effects

Dynasty / redraft / PPR / SF / TE-premium adjust **alert relevance notes and
severity bumps only**. They do not write valuation columns from articles.

## Valuation firewall proof

- `tests/test_news_intelligence_pass.py` + `tests/test_news_signal_audit.py`
- Changing headline / priority / source / news confidence / article count /
  alert severity leaves `score` / `news_factor` / risk unchanged until Sleeper
  `status` / `injury_status` changes.

Correct injury path:

1. Article → immediate News Alert (optional)
2. Sleeper structured status updates
3. `injury_level` → `risk_multiplier` / availability
4. Valuation changes through existing risk logic only

## Scenario matrix

Scenarios 1–18 covered in `tests/test_news_intelligence_pass.py`
(classification, confidence, entity/roster relationship, alert yes/no,
severity, dedupe/escalation, valuation changed = NO for article-only).

## Bugs found / fixed

1. `"active for"` substring matched inside `"inactive for"` → misclassified OUT as RETURN
2. Dead `role_change_note` / `depth_chart_note` plumbing — now populated from Sleeper structured cards only
3. Articles never reached Notification Center — wired cached-pool News Alert tiles
4. League switch left news alert escalation state — cleared with transient hygiene
5. Redraft relevance note skipped when injury already CRITICAL — league notes always attach

## Remaining unsupported / dead behavior

- Game Plan package cache **hit** path does not rebuild news alert tiles
- No write-back from articles into canonical depth/role valuation factors
- Independent multi-source corroboration is counted but does not yet mutate structured football state
- Google per-player fan-out still gated to News page (by design; Dashboard stays 0 live RSS)

## Performance

| Path | Expectation |
|---|---|
| Dashboard news alerts | `load_cached_news_pool()` only — **0** live RSS |
| Warm `fetch_news` | 0 live RSS when disk &lt; 20m (from #250) |
| Alert build | in-process classify + session dedupe; max 3 tiles |

## Required Q&A

1. **Can an article directly change player value?** No.
2. **Can an important injury article alert me before structured state updates?** Yes — News Alert from cached articles.
3. **What eventually causes the valuation change?** Structured Sleeper `status` / `injury_status` (and other canonical football fields), via risk/availability multipliers.
4. **Will a position-battle article alert me?** Yes, when roster-relevant, with uncertainty; not as confirmed starter.
5. **Can speculation incorrectly make someone a confirmed starter?** No (`confirmed_starter` requires official starter language and non-speculative confidence).
6. **Does the system know mine / FA / opponent?** Yes — roster relationship resolution against shared league context.
7. **Does dynasty/redraft/PPR/SF/TE-premium alter alert relevance?** Yes — relevance/severity only, not valuation writes.
8. **How are duplicates prevented from spamming?** `event_identity` + family cooldown + severity/confidence escalation gates.
9. **What happens when news providers fail?** Fail soft — empty cache / corrupt JSON / classifier exceptions → no tiles, Dashboard continues.
10. **What is still not trustworthy?** Package-hit alert refresh, structured depth write-back, and treating beat corroboration as football-state authority.

## Validation

See PR body / CI for full pytest, compileall, `git diff --check`, and perf budget.
