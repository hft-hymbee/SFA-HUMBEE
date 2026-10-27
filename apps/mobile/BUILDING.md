# Building the mobile apps

- [Android](#android): APKs for the emulator, phones and testers.
- [iOS](#ios): the Simulator and TestFlight.

Both platforms build the web app with the chosen environment's `apps/web/.env.*` (`local`, `qa`, `prod`). They check
that the env's API URL is `https://` and is the one baked into the bundle, then wrap it with Capacitor.

## Android

One command builds an APK for an environment:

```bash
pnpm mobile:apk:qa              # QA, debug-signed
pnpm mobile:apk:qa:release      # QA, release-signed (send this one to testers)
pnpm mobile:apk:prod            # prod, debug-signed
pnpm mobile:apk:prod:release    # prod, release-signed
pnpm mobile:apk:local           # API from apps/web/.env.local
```

Each run rebuilds the web export with that environment's `apps/web/.env.*`, syncs it into the Android project, runs Gradle,
and writes `apps/mobile/dist/Humbee-SFA-<env>-<versionName>-<versionCode>-<debug|release>.apk`.

- **versionName** is `NEXT_PUBLIC_APP_VERSION` from the env file.
- **versionCode** is the git commit count, so a newer build always installs over an older one.

QA and prod share the app id `com.humbee.sfa`, so a phone holds one of them at a time.

The script is `scripts/build-android.sh`. It checks your setup first and stops with a pointer back to this guide if
something is missing.

## Android: one-time machine setup (macOS)

Do these once. Each step ends with a check.

### 1. Java 21 and Android SDK on your shell path

Gradle needs **JDK 21**; Android Studio ships one. Add to `~/.zshrc`:

```bash
export JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home"
export ANDROID_HOME="$HOME/Library/Android/sdk"
export ANDROID_SDK_ROOT="$ANDROID_HOME"
export PATH="$JAVA_HOME/bin:$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$ANDROID_HOME/cmdline-tools/latest/bin:$PATH"
```

Then `source ~/.zshrc`.

Check: `java -version` prints `21.x` and `adb version` prints a version. A Homebrew `openjdk` (23+) elsewhere on your machine is
fine, as long as `JAVA_HOME` points at 21.

If Android Studio isn't installed: `brew install --cask android-studio`, open it once, and finish the setup wizard (it
downloads the SDK to `~/Library/Android/sdk`).

### 2. SDK packages

Android Studio → **Settings → Languages & Frameworks → Android SDK**:

- **SDK Platforms**: tick **Android 16 (API 36)**. The project compiles against 36.
- **SDK Tools**: tick **Android SDK Build-Tools 36.x**, **Android SDK Command-line Tools (latest)** and
  **Android SDK Platform-Tools**.

Click Apply, then accept the licences: `sdkmanager --licenses`.

Check: `sdkmanager --list_installed | grep -E "platforms;android-36|build-tools;36"` shows both.

### 3. Emulator

Android Studio → **Device Manager** → create a device (e.g. Medium Phone, API 35 or 36, arm64 image) or start an existing one.
From the terminal: `emulator -list-avds`, then `emulator -avd <name>`.

Check: `adb devices` lists `emulator-5554  device`.

### 4. Physical phone (optional)

On the phone, go to Settings → About phone and tap **Build number** 7 times. Then, in Settings → Developer options, turn on
**USB debugging**. Plug the phone in and accept the "Allow USB debugging" prompt.

Check: `adb devices` lists the phone as `device`, not `unauthorized`.

### 5. Repo dependencies

From the repo root:

```bash
pnpm install
pnpm --dir apps/mobile exec cap doctor
```

Check: `cap doctor` reports Android as looking great.

### 6. Release keystore (once, then keep it forever)

Release APKs are signed with a keystore that lives **outside the repo**. Android only installs an update if it is signed
with the same key, so if this file is lost, every tester has to uninstall and reinstall.

```bash
mkdir -p ~/.humbee
keytool -genkeypair -v -keystore ~/.humbee/humbee-sfa-release.jks \
  -alias humbee-sfa -keyalg RSA -keysize 2048 -validity 10000
cp apps/mobile/android/keystore.properties.example apps/mobile/android/keystore.properties
```

Edit `apps/mobile/android/keystore.properties`. Give the **absolute** path to the `.jks` (`~` isn't expanded), plus the
passwords you chose. The file is gitignored. Store the `.jks` and both passwords in the team password manager.

If the team already has a keystore, use that one instead of generating a new one.

Check: `pnpm mobile:apk:qa:release` succeeds.

## Android: installing

**Emulator or USB phone**

```bash
adb install -r apps/mobile/dist/<file>.apk
```

**Testers**

Send the release APK through Drive, Slack or WhatsApp. On their phone, opening the file asks them to allow
**Install unknown apps** for that app (Files, Chrome, WhatsApp…). They allow it once, then install.

**See which API the app talks to**

With the device connected, open `chrome://inspect` in Chrome on the Mac. Click **inspect** under *Humbee SFA* and watch
the Network tab.

## Android: troubleshooting

| Symptom | Fix |
| --- | --- |
| `Unsupported class file major version` or `requires Java 21` | `JAVA_HOME` isn't JDK 21. See step 1. |
| `Failed to find target with hash string 'android-36'` | Install SDK Platform 36. See step 2. |
| `SDK location not found` | `ANDROID_HOME` isn't set. See step 1. |
| "App not installed" / `INSTALL_FAILED_UPDATE_INCOMPATIBLE` | The installed copy was signed with a different key (debug vs release, or another machine's debug key). Uninstall it first: `adb uninstall com.humbee.sfa`. |
| `INSTALL_FAILED_VERSION_DOWNGRADE` | You're installing an older build over a newer one. Uninstall first, or add `-d` to `adb install`. |
| Script stops with "API URL … only allows https" | The env file's `NEXT_PUBLIC_SFA_API_BASE_URL` is `http://`. The app blocks cleartext and mixed content, so give the API an https URL. |
| App opens but every request fails on a `local` build | `localhost` on a device means the device itself. Point `.env.local` at your Mac's LAN address or a tunnel, over https. |
| App shows an old UI | Don't run Gradle by hand after changing web code. The script always rebuilds the web export first. |
| `adb devices` shows `unauthorized` | Unplug the phone, revoke USB debugging authorisations in Developer options, plug it back in and accept the prompt. |

## iOS

```bash
pnpm mobile:ios:sim:qa        # run QA on the iOS Simulator (no Apple account needed)
pnpm mobile:ios:sim:prod      # run prod on the Simulator
pnpm mobile:ipa:qa            # archive QA and upload it to TestFlight
pnpm mobile:ipa:prod          # archive prod and upload it to TestFlight
pnpm mobile:ipa:qa:file       # archive QA and save an .ipa to apps/mobile/dist (no upload)
pnpm mobile:ipa:prod:file
```

- **Version** (`CFBundleShortVersionString`) is `NEXT_PUBLIC_APP_VERSION` from the env file.
- **Build number** (`CFBundleVersion`) is `<git commit count>.<yyMMdd>.<HHmm>`, e.g. `19.261027.1530`. QA and prod upload
  to the same App Store Connect app, and every upload needs a new build number, so the time is part of it.
- QA and prod share the bundle id `com.humbee.sfa`. In TestFlight, tell builds apart with the *What to Test* note and
  separate tester groups.

The scripts are `scripts/run-ios-sim.sh` and `scripts/build-ios.sh`. They check your setup first.

## iOS: one-time setup

Step 1 is all you need for the Simulator. Steps 2–6 are needed for TestFlight.

### 1. Xcode and simulators

Install Xcode from the Mac App Store and open it once. Then:

```bash
sudo xcodebuild -license accept
xcodebuild -runFirstLaunch
```

Xcode → Settings → Components: install the iOS platform it offers.

Check: `xcrun simctl list devices available` lists iPhones. The script uses "iPhone 17 Pro" on the newest iOS runtime, or
the first iPhone there. Choose another with `HUMBEE_IOS_SIM="iPhone Air" pnpm mobile:ios:sim:qa`.

### 2. Sign in to Xcode with the company Apple ID

Xcode → Settings → Accounts → **+** → Apple ID. The company team appears with your role. You need **Admin** or **App
Manager** to create distribution certificates and upload builds.

### 3. Team ID

developer.apple.com → Account → Membership details → **Team ID** (10 characters).

It's not secret. Set it once in the project: Xcode → open `apps/mobile/ios/App/App.xcodeproj` → target **App** → Signing &
Capabilities → Team. Commit the `project.pbxproj` change. Until then, pass it per build:
`HUMBEE_IOS_TEAM_ID=ABCDE12345 pnpm mobile:ipa:qa`.

### 4. Bundle id

developer.apple.com → Certificates, IDs & Profiles → Identifiers. Check that `com.humbee.sfa` exists; if not, **+** →
App IDs → App → Bundle ID `com.humbee.sfa`, description "Humbee SFA".

### 5. App Store Connect app record

appstoreconnect.apple.com → Apps → **+** → New App:

- Platform **iOS**, name **Humbee SFA**, language English, bundle id `com.humbee.sfa`, SKU `humbee-sfa`.
- Access: Full Access.

The first upload fails without this record.

### 6. TestFlight testers

App Store Connect → Humbee SFA → TestFlight:

- **Internal testing:** up to 100 people who are App Store Connect users on the team. No review. Create a group (e.g.
  "QA testers") and add them.
- **External testing:** anyone by email or public link, up to 10,000. The first build in a group goes through Beta App
  Review, which usually takes about a day.

Testers install the **TestFlight** app from the App Store and accept the email invite.

## iOS: shipping a build to TestFlight

1. `pnpm mobile:ipa:qa` (or `:prod`). The first run creates the Apple Distribution certificate and provisioning profile
   automatically (`-allowProvisioningUpdates`). macOS may ask for your login password to save the certificate to the
   keychain; choose **Always Allow**.
2. Wait for the email saying the build has finished processing (usually 10–30 minutes).
3. App Store Connect → TestFlight → the build → **What to Test**: say whether it's the **QA** or **PROD** build.
4. Add the build to the tester group. Testers get a notification in TestFlight and tap **Install**.

`pnpm mobile:ipa:qa:file` does the same archive but saves the `.ipa` to `apps/mobile/dist/` instead of uploading it.
Upload that file later with Apple's **Transporter** app.

Inspect a running app: Safari → Settings → Advanced → *Show features for web developers*, then Safari → Develop →
the Simulator or iPhone → localhost.

## iOS: troubleshooting

| Symptom | Fix |
| --- | --- |
| `Unable to find a destination matching the provided destination specifier` | The simulator is on an iOS runtime this Xcode can't build for. The script picks the newest runtime; install it in Xcode → Settings → Components. |
| App icon appears but the Simulator shows the home screen | Tap **Humbee SFA**. A freshly booted simulator sometimes brings the home screen up over the app. |
| "No Apple team ID" | Step 3. |
| `No Account for Team` / `No profiles for 'com.humbee.sfa' were found` | Xcode isn't signed in with an Apple ID on that team (step 2), or the team ID is wrong (step 3). |
| `No signing certificate "iOS Distribution" found` | Your role can't create certificates. Ask for Admin or App Manager. |
| Upload fails with "No suitable application records were found" | Create the App Store Connect app record (step 5). |
| Upload fails with "The bundle version must be higher than the previously uploaded version" | Run the command again; the build number includes the time. |
| Script stops with "API URL … only allows https" | iOS blocks plain `http://` API calls. Give the env an https URL. |
| Build is "Missing Compliance" in TestFlight | `ITSAppUsesNonExemptEncryption` is set to `false` in `Info.plist`, so this shouldn't appear. If it does, answer "None of the algorithms mentioned above". |

Not covered yet, needed before an App Store (public) release: the app's `PrivacyInfo.xcprivacy`, the App Privacy answers
in App Store Connect, and a review of the "Always" location permission string (v1 uses foreground location only).
