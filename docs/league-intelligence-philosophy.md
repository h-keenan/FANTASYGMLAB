# League Intelligence

DynastyGM does not display news. It explains why news matters to your league.

The feed is a presentation workflow over existing curated news and league data.
It does not score sentiment, change player values, or create football
recommendations. Each item answers four questions with only proven context:

1. What happened?
2. Which player is affected?
3. Where does that player sit in this league?
4. What is the conservative next action?

## Context contract

The feed may show `Owned by you`, `Owned by <team>`, or `Available on waivers`
only when the matched player has a stable player ID and the active league's
existing roster map proves that state. Missing identity or ownership is omitted.

Action labels are intentionally narrow:

- `Waiver Watch` means the matched player is absent from every active roster.
- `Injury Monitor` means the existing news matcher classified the item as
  injury/status-related.
- `Monitor` is the fail-safe label for every other supported item.

These are presentation labels, not outputs from Trade Hub, Waivers, Team Needs,
valuation, ranking, or archetype engines.

## Interaction

The timeline defaults to a fast chronological scan. “Why this matters” lazily
reveals the longer source summary, matched signal, and league ownership context.
The affected player uses the universal Football Asset and opens the canonical
Player Quick View. External reports use safe HTTP(S) destinations.

## Performance and safety

The player index is limited to names present in the curated feed and ownership
is indexed once per invocation. Styling is loaded once through the shared
application stylesheet. Expanded explanations are rendered only while open.
Feed state is namespaced by a stable article identity and is not persisted
outside the Streamlit session.
