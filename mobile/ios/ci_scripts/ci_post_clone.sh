#!/bin/sh
set -e

# Xcode Cloud clones the whole FANTASYGMLAB monorepo; the Expo app lives
# under mobile/. CI_WORKSPACE is set by Xcode Cloud to the repo root.
cd "$CI_WORKSPACE/mobile"

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
