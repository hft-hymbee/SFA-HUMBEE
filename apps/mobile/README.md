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

See [`../../ARCHITECTURE.md`](../../ARCHITECTURE.md) for how the client, shell and API fit together.

## Prerequisite: `apps/web` must be statically exportable

Capacitor serves a folder of static assets, so `apps/web` runs with `output: 'export'`. That rules
out middleware, Server Actions, intercepting routes, `rewrites`/`redirects`/`headers`, request-time
`cookies()`/`headers()`, and the default image loader.

None of it hurts — the SFA app is a token-authenticated SPA over FastAPI with client-side data
fetching and client-side route guards. Keep it that way: a server-only feature breaks the native build.

## Setup (first time)

The Android and iOS projects are generated and committed.

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

The API URL is baked into the web export. Set `NEXT_PUBLIC_SFA_API_BASE_URL` for the target environment
on the web build (see [`../../DEPLOY.md`](../../DEPLOY.md), Mobile); otherwise the build reads
`apps/web/.env.local`.

## Directories

| Path | Holds |
| --- | --- |
| `capacitor.config.ts` | App id, name, `webDir`, plugin config |
| `android/` | Generated Android project (committed) |
| `ios/` | Generated iOS project (committed); set your own signing team in Xcode |

## Store-review risks for this app

Two of these have historically caused rejections.

| Risk | Status |
| --- | --- |
| **Background location** — The manager's team-day view renders travel legs between outlets, implying all-day location capture. Apple needs an "Always" justification; Play needs a declaration form, demo video and prominent disclosure. | ✅ **Decided — no background tracking in v1.** Use foreground-only location events. |
| **Public stores vs enterprise distribution** — Apple Business Manager custom apps + Managed Google Play skip public review entirely, and most SFA deployments qualify. | ⚠️ **Open:** choose public stores or enterprise distribution before the first release. |
| **Account deletion** (Apple 5.1.1(v)) | Accounts are Admin-provisioned with no self-signup, which normally exempts it — state this in review notes. |
| **Privacy declarations** — GPS traces, phone numbers, GST/PAN photos | Declare location, phone number and document-photo collection in `PrivacyInfo.xcprivacy` and Play Data Safety. |
| **Field devices don't take store updates** | Capacitor live-updates can ship web-layer fixes without review. Native changes still need a release. |

**No push notifications** — notifications are in-app only. No push plugin, no device tokens, no permission prompt.

## Windows build

```powershell
corepack pnpm --filter web build
corepack pnpm --filter mobile sync
$env:ANDROID_HOME = "$env:LOCALAPPDATA\Android\Sdk"
$env:ANDROID_SDK_ROOT = $env:ANDROID_HOME
$env:JAVA_HOME = "<path-to-jdk-21>"
cd apps/mobile/android
.\gradlew.bat assembleDebug --no-daemon
```
