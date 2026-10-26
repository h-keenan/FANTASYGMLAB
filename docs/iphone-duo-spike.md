# iPhone Duo / Xcode 27.1 build spike (2026-10-25)

Status: research only. No build or simulator test was possible (see 1). Companion to `docs/app-store-assets-plan.md` section 1.5 and 6.

## 1. Local tooling (this Mac)

- `xcode-select -p`: `/Applications/Xcode.app/Contents/Developer`
- Installed: Xcode 26.0.1 (build 17A400) only. No Xcode 27.x.
- Simulator runtimes: iOS 26.0 only. Device types: no iPhone Duo (only Vision Pro matched the grep).
- Result: the build + Duo-screenshot part (task 3) was NOT run. Nothing was downloaded or installed. No worktree build, no fastlane, no signing.

## 2. Compatibility research

Sources (Expo first-party):
- Upgrade guide, Oct 21 2026: https://expo.dev/blog/how-to-upgrade-to-sdk-58
- SDK 58 beta changelog: https://expo.dev/changelog/sdk-58-beta
- Xcode 27 / Device Hub post: https://expo.dev/blog/xcode-27-device-hub-expo-device-hub

Findings:
- Expo SDK 58 is the release that "brings iOS 27 support and React Native 0.88" (stable, out as of Oct 21 2026). It "is ready for" iPhone Duo form factors.
- iOS 27 SDK requires the UIKit scene-based lifecycle and makes iPhone apps resizable. SDK 58 `expo prebuild` generates `SceneDelegate.swift` and a `UIApplicationSceneManifest`; the scene delegate creates the window.
- iOS 27: `requireFullScreen` no longer opts out of resizing; `ScreenOrientation.lockAsync` may have no effect while resizable.
- EAS Build: `sdk-58` and `latest` image aliases point to the Xcode 27.1 image (before that, `latest` was Xcode 26.6).
- Xcode 27 replaces Simulator.app with Device Hub; Expo CLI handles it from SDK 58 (SDK 56/57 got Device Hub detection only; "On Xcode 26 nothing changes").
- NOT found in any source: that SDK 54 (our version, RN 0.81.5) gets iOS 27 SDK / Xcode 27 support. The upgrade guide covers only 57 -> 58. Treat SDK 54 + Xcode 27.1 as unsupported/unverified until tested; a stock SDK 54 build will likely crash or misbehave on launch without the scene lifecycle (inference from the beta changelog, not tested).
- SDK 58 breaking changes (per guide): Strict TypeScript API default (no `react-native/Libraries/*` deep imports), removed `InteractionManager`, `Touchable` root export, `Modal` `animated` prop, `StatusBar` `backgroundColor`/`translucent`/`networkActivityIndicatorVisible`; `ImageBackground` deprecated; expo-router native-tabs rename; macOS unsupported.
- Not verified by me: Apple's own wording on the Xcode 27.1 requirement (see plan section 1.5 for the Apple sources and the "any app submitted" vs "iOS 27.1 SDK" discrepancy).

## 3. Upgrade path (54 -> 58)

Four SDK majors (55, 56, 57, 58), RN 0.81 -> 0.88. Do step by step, each on a branch with a simulator smoke test; do not jump blind.
1. 54 -> 55 -> 56 -> 57: follow each Expo "how to upgrade" guide. Needs each guide read; I did not fetch 55-57 notes.
2. 57 -> 58: scene lifecycle, Strict TS, removed APIs above.
3. Release build on EAS image (Xcode 27.1) or local Xcode 27.1; test on Duo simulator via Device Hub.

## 4. Repo-specific risks (from `mobile/` inspection)

- `mobile/ios` is committed (`mobile/ios/FantasyGMLab.xcodeproj` is tracked), so prebuild does not regenerate it: the AppDelegate -> SceneDelegate migration must be applied by hand (or regenerate with `expo prebuild --clean` and re-port customizations). Highest-risk item.
- `app.json`: `"orientation": "portrait"` and `supportsTablet: true`. Portrait lock may be ignored on resizable iOS 27; layouts must tolerate arbitrary window sizes, including the near-square inner display (2007x2853) and landscape.
- Custom plugin `plugins/withIosMinDeploymentTarget.js` and `deploymentTarget: 15.1` need rechecking against SDK 58's minimum.
- Native deps to re-verify at SDK 58: `react-native-reanimated` (4.1) + `react-native-worklets` (0.5.1), `react-native-screens`, `expo-notifications`, plus any IAP/RevenueCat module.
- Only 0 matches in `src/` for `InteractionManager`, `ImageBackground`, `networkActivityIndicatorVisible` at grep time; `Modal animated=` and StatusBar prop usage were not exhaustively checked.
- Shipping cost: April 2027 Duo screenshot requirement may force this upgrade before then (per plan); App Store submission must use an Xcode 27.x build anyway for the Duo badge.

## 5. Layout checks still to do (once Xcode 27.1 + Duo sim exist)

Safe areas/insets on outer and inner display, resizing across poses, tablet-like layouts at inner size, keyboard behavior, modals/sheets, bottom nav, GM orb placement (see orb history), landscape. Capture 1398x2034 and 2007x2853 screenshots from the simulator.

## 6. Next steps (needs Zach)

1. Install Xcode 27.1 (a human download/sign-in) so the spike can be completed.
2. Decide whether to start the SDK 54 -> 58 upgrade now or closer to April 2027.
