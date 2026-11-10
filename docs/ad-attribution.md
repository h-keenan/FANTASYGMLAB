# Ad attribution capture

`web-next/src/lib/attribution.ts` keeps the FIRST touch per browser (localStorage) and merges it into
every analytics event (`lib/analytics.ts`), so signup/league-connect/checkout events all carry it:
`utm_source`, `utm_medium`, `utm_campaign`, `utm_content`, `utm_term`, `referrer_host`, `has_ref`,
`click_id` (network kind: gclid, fbclid, ttclid, msclkid, rdt, gbraid, wbraid) and `click_id_value`
(the id itself, case preserved, max 200 chars).

Server side, `modules/launch_analytics.py` allowlists those keys and stores them in the existing
`analytics_events.props` jsonb column. **No schema change or SQL migration is needed**, and nothing
breaks if the keys are absent.

Query example (Supabase SQL editor):
`select props->>'utm_campaign', props->>'utm_content', count(*) from analytics_events where event='signup_completed' group by 1,2;`

Still NOT done (needs Zach / product decision): sending conversions back to ad networks
(Meta CAPI, Google offline conversions, TikTok Events API). Those need each network's credentials
and an account/pixel id; the click id values are now captured so that can be built from the billing
webhook. The mobile app still ships analytics OFF, so app installs from ads carry no attribution.
Privacy policy now discloses the campaign parameters / click identifier (counsel should review).
