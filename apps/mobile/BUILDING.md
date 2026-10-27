# Building the Android APK

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

## One-time machine setup (macOS)

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

## Installing

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

## Troubleshooting

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
