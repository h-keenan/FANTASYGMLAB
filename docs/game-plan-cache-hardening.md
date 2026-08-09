# Game Plan cache hardening (#222)

## Issues

1. **Serialization crash:** `cached_league_context` returned `TradeTrustContext` defined in `app.py` (`__main__`). Streamlit `@st.cache_data` pickle failed across reruns (`UnserializableReturnValueError`).
2. **Fingerprint drift:** package/trade signatures changed across presentation-only remounts (`post_usable_auth_save`, UI), causing repeated 3–5s trade builds.

## Fixes

### TradeTrust ownership

| Layer | Contract |
|---|---|
| `modules/trade_trust.py` | Canonical `TradeTrustContext` type (not `__main__`) |
| `st.cache_data` (`cached_league_context`) | Stores **serialized dict** only (`serialize_trade_trust_context`) + `cache_schema_version` |
| Runtime / Trust enforcement | `hydrate_trade_trust_context` at boundary |
| Process memo | May hold dict; hydrate before use |

### Fingerprint stability

Removed / ignored ephemeral inputs:

- `startup_mode` from package + league process signatures
- `startup_complete` from trade maturity digest
- account_scope from package lifecycle (use `football_digest`; account keyed separately)

Canonicalized: sorted roles/untouchables, casefolded entitlement, fingerprint version = 2.

### Diagnostics

`startup_cache_event` rows:

- `game_plan_package_fingerprint_components`
- `trade_inventory_fingerprint_components`

Hashed component prefixes only (no PII).

## Expected READY session

1. Package miss once → build
2. Process league/trade miss once then hit
3. `post_usable_auth_save` → **package HIT**
4. Alerts / GM / PQV / Dashboard revisit → **package HIT**
5. No repeated trade inventory rebuilds
