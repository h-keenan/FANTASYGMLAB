#!/bin/sh
set -e

# Xcode Cloud clones the whole FANTASYGMLAB monorepo; the Expo app lives
# under mobile/. CI_PRIMARY_REPOSITORY_PATH is Apple's documented Xcode
# Cloud env var for the repo checkout root (CI_WORKSPACE is not a real
# Xcode Cloud variable — that was a GitHub Actions naming assumption that
# leaked in here and silently evaluated to an empty string, so `cd` landed
# on `/mobile` instead of the actual checkout path).
cd "$CI_PRIMARY_REPOSITORY_PATH/mobile"

# Xcode Cloud's macOS images include Homebrew but not necessarily the Node
# version this project expects.
brew install node@20
export PATH="/opt/homebrew/opt/node@20/bin:$PATH"

npm ci

# Same Continuous Native Generation the Fastlane pipeline uses (see
# fastlane/Fastfile's ensure_native_project): ios/ is never hand-maintained,
# it's regenerated fresh from app.json + package.json on every build so
# signing config and native project state can't drift. The ios/ directory
# committed to git is only a bootstrap snapshot so Xcode Cloud has a project
# to detect and build a workflow against — this --clean prebuild overwrites
# it before every real build.
npx expo prebuild --platform ios --clean --non-interactive

cd ios
pod install
