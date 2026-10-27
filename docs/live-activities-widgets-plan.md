# iOS Live Activities + widget plan

Status: implemented behind two OFF switches, nothing built or signed. Requested by coridian_.

## Scope
- Live Activity (lock screen + Dynamic Island): live head-to-head score for the user's active (last-opened) league while that league's NFL games are running.
- Home-screen widget (small/medium): latest unread league alerts (waiver/trade-relevant news from `/alerts`). Trade-target tiles are a follow-up: `gm-targets` returns ids only and needs client-side enrichment the widget cannot do.
- Data is always real Sleeper points (existing `/matchup` pipeline). No projections shown as scores, nothing fabricated; when either side has no live data the activity does not start.

## Approach (Expo SDK 54)
- Hand-written config plugin `mobile/plugins/withLiveActivities.js` (not expo-apple-targets: adds a dependency we cannot verify without a build, and the repo already regenerates `ios/` via `prebuild --clean`). It adds a WidgetKit extension target `FantasyDeskWidgets`, embeds it, adds the App Group entitlement, `NSSupportsLiveActivities`, and compiles a small RN bridge into the app target. Swift sources: `mobile/native/live-activity/`.
- Plugin is a no-op unless `FANTASYDESK_LIVE_ACTIVITIES=1` at prebuild, so production builds are unchanged. JS side is off unless `EXPO_PUBLIC_LIVE_ACTIVITIES_ENABLED=1` and the native module exists.
- Extension deployment target 16.2 (ActivityKit content API); app stays 15.1, bridge guards with `#available`.
- Widget reads a JSON snapshot the app writes into the App Group (`group.com.fantasygmlab.app`); it never fetches.
- Android: iOS-only feature, explicit parity exception. Equivalent later: an ongoing (foreground-service-less) notification updated from the same `/live-activity` endpoint via expo-notifications, plus a Glance home widget via a config plugin. Not built here.

## Updates: local now, APNs push later
- Phase 1 (this PR): local `Activity.update` while the app is foregrounded (60 s poll). Honest limit: nothing updates once iOS suspends the app.
- Phase 2: `pushType: .token`, bridge forwards the per-activity push token to a new backend endpoint; a worker sends APNs `liveactivity` pushes (apns-push-type `liveactivity`, topic `<bundle>.push-type.liveactivity`, token-based .p8 auth, ~15 min cadence during games, `dismissal-date` at final). Needs backend job + stored tokens + APNs key.

## Backend
`GET /v1/leagues/{id}/live-activity` (`modules/live_activity.py`): trims `_build_matchup` to team names, real points, margin, win probability, `game_state`, and `should_run` (true only while games are live/between games). Same 200 + `reason` not-ready contract. Tests: `tests/test_live_activity.py`.

## Human work required
1. Apple Developer portal: register App Group `group.com.fantasygmlab.app`; enable it on `com.fantasygmlab.app`; create App ID `com.fantasygmlab.app.widgets` with the same group; regenerate provisioning profiles for both (fastlane/Xcode Cloud signing must cover the second bundle id).
2. Run one prebuild with `FANTASYDESK_LIVE_ACTIVITIES=1`, open in Xcode, fix any compile issues (Swift is unverified), test on a physical device (Live Activities do not run reliably in Simulator).
3. Set `EXPO_PUBLIC_LIVE_ACTIVITIES_ENABLED=1` in the build env; App Store review notes for the widget/Live Activity; update screenshots if desired.
4. Phase 2 only: APNs auth key (.p8) as a backend secret.

## Risks
- Swift/Xcode project edits were validated only by parsing the real pbxproj with the `xcode` lib and TS/Node tests; no compile, no signing. Expect a fix-up pass on first build.
- Fastlane/Xcode Cloud signing for a second target is the likeliest first-build failure.
- Local-only updates are stale when the app is backgrounded until Phase 2.
- Analytics stays OFF (no events added). Guests never start an activity.
- Battery/rate: 60 s foreground poll hits `/matchup` machinery; Phase 2 should move to server-side polling.
