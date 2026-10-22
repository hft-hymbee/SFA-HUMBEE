# apps/mobile — Capacitor native shell

Wraps the Humbee SFA web app for the **App Store** and **Play Store**.

> **This package contains no application code.** Screens, routing, state and device-capability
> wrappers all live in `apps/web`. This directory holds only native configuration, the generated
> `android/` and `ios/` projects, signing/store metadata, and release lanes.

## Why the split

`@capacitor/*` plugins ship **web implementations**, so a single bundle from `apps/web` runs both in
a browser and inside the native shell. That means device access belongs in
`apps/web/src/shared/capabilities/`, and only the native project trees belong here — which keeps the
web app deployable without native artifacts and gives the two different CI lanes and owners.

Full rationale: [`../../docs/architecture/target-architecture.md`](../../docs/architecture/target-architecture.md) §4.

## Prerequisite: `apps/web` must be statically exportable

Capacitor serves a folder of static assets, so `apps/web` runs with `output: 'export'`. That rules
out middleware, Server Actions, intercepting routes, `rewrites`/`redirects`/`headers`, request-time
`cookies()`/`headers()`, and the default image loader.

None of it hurts — the SFA app is a token-authenticated SPA over FastAPI with client-side data
fetching and client-side route guards. But it must be honoured from the start (`R-STRUCT-01`).

## Setup (first time)

The Android project is generated and committed. The iOS project remains deferred.

```bash
pnpm install
pnpm --filter web build
pnpm --filter mobile sync
```

## Everyday build

```bash
pnpm --filter web build       # produces apps/web/out
pnpm --filter mobile sync     # copies the export and updates Android plugins
cd apps/mobile/android
./gradlew assembleDebug       # APK: app/build/outputs/apk/debug/app-debug.apk
```

Run the web build before every sync so the APK receives the latest frontend assets.

## Directories

| Path | Holds |
| --- | --- |
| `capacitor.config.ts` | App id, name, `webDir`, plugin config |
| `android/` | Generated Android project (committed) |
| `ios/` | Reserved iOS scaffold; native generation is deferred |
| `resources/` | `icon.png` + `splash.png` sources for asset generation |
| `fastlane/` | Store upload lanes. **No secrets** — signing keys come from CI secrets or a local keychain |
| `store/` | Listing copy, screenshots, and the privacy declarations (Apple `PrivacyInfo.xcprivacy`, Play Data Safety) |

## Store-review risks for this app

Two of these have historically caused rejections. Detail and mitigations in
[the architecture source](../../docs/architecture/target-architecture.md#72-open-owner-confirmations).

| Risk | Status |
| --- | --- |
| **Background location** — `S-TEAM2` renders travel legs between outlets, implying all-day location capture. Apple needs an "Always" justification; Play needs a declaration form, demo video and prominent disclosure. | ✅ **Decided — no background tracking in v1.** Use foreground-only location events (see decision register D-011). |
| **Public stores vs enterprise distribution** — Apple Business Manager custom apps + Managed Google Play skip public review entirely, and most SFA deployments qualify. | ⚠️ **Open owner confirmation:** see `OQ-003` in [`target-architecture.md` §7.2](../../docs/architecture/target-architecture.md#72-open-owner-confirmations). |
| **Account deletion** (Apple 5.1.1(v)) | Accounts are Admin-provisioned with no self-signup, which normally exempts it — state this in review notes. |
| **Privacy declarations** — GPS traces, phone numbers, GST/PAN photos | Derive from [`02-rbac-and-scoping.md`](../../docs/features/02-rbac-and-scoping.md) §6. |
| **Field devices don't take store updates** | Capacitor live-updates can ship web-layer fixes without review. Native changes still need a release. |

**No push notifications** — notifications are in-app only (decision `D-004` in [`target-architecture.md` §7.1](../../docs/architecture/target-architecture.md#71-decided)). No push plugin, no device tokens, no permission prompt.


To build android apk:

corepack pnpm --filter web build

corepack pnpm --filter mobile sync

$env:GRADLE_USER_HOME = "C:\Users\Admin\.gradle"
$env:ANDROID_HOME = "$env:LOCALAPPDATA\Android\Sdk"
$env:ANDROID_SDK_ROOT = $env:ANDROID_HOME
$env:JAVA_HOME = "C:\Program Files\Microsoft\jdk-21.0.12.101-hotspot\"
.\gradlew.bat assembleDebug --no-daemon