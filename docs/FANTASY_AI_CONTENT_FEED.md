# Fantasy AI read-only content export

GET /v1/content/feed serves a general-public feed, independently of Supabase user sessions. Configure FGL_CONTENT_TOKEN_SHA256 with the SHA-256 digest of a separate random token (at least 32 characters). Fantasy AI keeps the original token locally and sends Authorization: Bearer. Missing configuration returns 503; invalid credentials return 401. This credential cannot access user/league routes.

The feed contains canonical base dynasty values, actual FGL position-relative OVR ratings computed over the full eligible position pool, Sleeper global add activity, and curated general NFL news. Source and export timestamps are separate. Player-cache exports older than 24 hours are held. A five-minute process cache prevents concurrent duplicate work.

Trending adds are watch candidates, not a claim that a player is available in every league. ESPN public ownership figures are supplied when the canonical player ID or unique name/position/team match is trustworthy and the provider timestamp is within 24 hours. Figures retain the ESPN platform and Fantasy football population label; they are not Sleeper percentages. An optional FGL_CONTENT_ROSTERED_FILE can supply a separately labeled population. Unknown, stale, or ambiguous matches remain null, never zero. No private roster, account, budget, league, or billing fields are exported.

Self-hosted setup: place only FGL_CONTENT_TOKEN_SHA256 in /opt/fantasygmlab/.env. The mobile-api service already loads this file via Docker Compose env_file. Recreate the mobile-api service to activate it. The Caddy route and port configuration do not change.
