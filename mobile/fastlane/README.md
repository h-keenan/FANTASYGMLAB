fastlane documentation
----

# Installation

Make sure you have the latest version of the Xcode command line tools installed:

```sh
xcode-select --install
```

For _fastlane_ installation instructions, see [Installing _fastlane_](https://docs.fastlane.tools/#installing-fastlane)

# Available Actions

## iOS

### ios app_status

```sh
[bundle exec] fastlane ios app_status
```

Check whether the App Store Connect app record exists

### ios create_app

```sh
[bundle exec] fastlane ios create_app
```

Create the App ID (Developer Portal) and app record (App Store Connect) — pure API-key auth, no Apple ID/2FA

### ios certs

```sh
[bundle exec] fastlane ios certs
```

Sync (or, run by a human, rotate) signing certs/profiles via match. Read-only in CI.

### ios beta

```sh
[bundle exec] fastlane ios beta
```

Build and upload a TestFlight build

----


## Android

### android beta

```sh
[bundle exec] fastlane android beta
```

Build and upload a Play internal-testing build

----

This README.md is auto-generated and will be re-generated every time [_fastlane_](https://fastlane.tools) is run.

More information about _fastlane_ can be found on [fastlane.tools](https://fastlane.tools).

The documentation of _fastlane_ can be found on [docs.fastlane.tools](https://docs.fastlane.tools).
