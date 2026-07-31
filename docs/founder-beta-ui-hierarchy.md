# Founder Beta UI hierarchy

This pass standardizes Dashboard, League Overview, Trade Board, My Team,
Waivers, Player Explorer, and Premium without changing their workflows or
football outputs.

## Canonical hierarchy

| Level | Role | Token | Before | Founder Beta |
|---|---|---|---|---|
| 1 | Page eyebrow | `--type-page-eyebrow-size` | badge/caption values varied by shell | 0.6875rem |
| 2 | Page title | `--type-page-title` | 1.5rem token overridden as high as 5rem | clamp(1.75rem, 4vw, 2.5rem) |
| 3 | Page description | `--type-body-explanation` | body and caption variants | 0.875rem / 1.45 |
| 4 | Section eyebrow | `--type-section-eyebrow-size` | caption or badge | 0.6875rem |
| 5 | Section title | `--type-section-title` | 1.125rem plus one-off clamps to 1.8rem | clamp(1.125rem, 2vw, 1.5rem) |
| 6 | Card title | `--type-card-title` | page-specific body/title sizes | 0.875rem / 1.2 |
| 7 | Primary metric | `--type-primary-metric` | multiple monospace sizes | 1.375rem |
| 8 | Supporting metadata | `--type-supporting-metadata` | 0.6875–0.875rem | 0.75rem / 1.35 |
| 9 | Body explanation | `--type-body-explanation` | body/caption mixtures | 0.875rem / 1.45 |
| 10 | Badge/status | `--type-badge-size` | several local declarations | 0.6875rem |

Only eyebrows, section labels, and compact statuses use forced uppercase.
Page and section titles retain the existing command-center uppercase treatment
but now share one scale and normal word wrapping.

## Removed one-off presentation

- The late 2.4–5rem workspace-title override no longer controls rendered size.
- The Dashboard-only 1.75–2.35rem mobile title scale is superseded by the
  canonical mobile page-title token.
- The Dashboard-only 1.35–1.8rem section-title scale is superseded by the
  canonical mobile section-title token.
- Page-specific card padding, border, radius, and mobile width differences are
  normalized at the final shared layer.
- League Overview's duplicate “Teams Snapshot” introduction is omitted on the
  Rankings surface.
- Repeated Power Rank and Franchise Rank captions are removed after the
  definitions have already appeared in the concept band.

## League Overview terms

- **Power Rank:** current starter strength, usable depth, and present roster value.
- **Franchise Rank:** total player value plus owned draft capital.
- **Strategy:** recommended direction; it is not a rank.
- **Archetype:** descriptive roster shape; it is not a rank or strategy switch.

## Performance interpretation

Navigation remains Streamlit rerun-based. Destination controls use callbacks and
produce one script run with no explicit extra rerun in the controlled warm
measurement. Expensive data remains behind existing cache boundaries; this
visual pass does not change them.

### Controlled warm measurements

Environment: local logged-out Streamlit AppTest, same process/session after
prewarming, 10 samples. These figures isolate application server work from the
larger AppTest harness overhead and are not deployed-browser timings.

| Interaction | Before median server | After median server | Before median wall | After median wall | Explicit reruns |
|---|---:|---:|---:|---:|---:|
| Dashboard → My Team | 115.4 ms | 115.5 ms | 1,245.5 ms | 1,244.2 ms | 0 |
| Warm page render | — | 114.3 ms | — | 1,217.5 ms | 0 |

The change is directionally neutral: the presentation layer neither removes nor
adds a Streamlit script run. Destination changes still require one normal
framework rerun. Tabs, disclosures, and dialogs retain their existing lazy
boundaries; no new explicit `st.rerun()` call was added.
