#!/usr/bin/env bash
# Build an Android APK for one environment.
#   Usage: scripts/build-android.sh <local|qa|prod> [debug|release]
# Output: apps/mobile/dist/Humbee-SFA-<env>-<versionName>-<versionCode>-<type>.apk
# First-time machine setup: see apps/mobile/BUILDING.md.
set -euo pipefail

BUILD_TYPE="${2:-debug}"

source "$(dirname "${BASH_SOURCE[0]}")/lib/web-build.sh"
ANDROID_DIR="$MOBILE_DIR/android"
STUDIO_JBR="/Applications/Android Studio.app/Contents/jbr/Contents/Home"
COMPILE_SDK=36

resolve_env "${1:-}" "$0 <local|qa|prod> [debug|release]"
case "$BUILD_TYPE" in
  debug)   GRADLE_TASK="assembleDebug" ;;
  release) GRADLE_TASK="assembleRelease" ;;
  *) fail "build type must be 'debug' or 'release', got '$BUILD_TYPE'" ;;
esac

step "Preflight"

java_major() { "$1/bin/java" -version 2>&1 | awk -F'"' '/version/ {split($2, v, "."); print v[1]; exit}'; }
if [[ -z "${JAVA_HOME:-}" || ! -x "${JAVA_HOME}/bin/java" || "$(java_major "$JAVA_HOME")" != "21" ]]; then
  if [[ -x "$STUDIO_JBR/bin/java" && "$(java_major "$STUDIO_JBR")" == "21" ]]; then
    warn "JAVA_HOME is not a JDK 21; using Android Studio's bundled JDK at $STUDIO_JBR"
    export JAVA_HOME="$STUDIO_JBR"
  else
    fail "Gradle needs JDK 21. Set JAVA_HOME to a JDK 21 (Android Studio's bundled JDK works). See BUILDING.md step 1."
  fi
fi
echo "JDK: $JAVA_HOME"

export ANDROID_HOME="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-$HOME/Library/Android/sdk}}"
export ANDROID_SDK_ROOT="$ANDROID_HOME"
[[ -d "$ANDROID_HOME" ]] || fail "Android SDK not found at $ANDROID_HOME. Set ANDROID_HOME. See BUILDING.md step 1."
[[ -d "$ANDROID_HOME/platforms/android-$COMPILE_SDK" ]] \
  || fail "Android SDK Platform $COMPILE_SDK is not installed. Install it in Android Studio > Settings > Android SDK. See BUILDING.md step 2."
echo "Android SDK: $ANDROID_HOME"

if [[ "$BUILD_TYPE" == "release" ]]; then
  [[ -f "$ANDROID_DIR/keystore.properties" ]] \
    || fail "Release builds need android/keystore.properties. Copy keystore.properties.example and fill it in. See BUILDING.md step 6."
fi

load_env
VERSION_NAME="$APP_VERSION"
VERSION_CODE="$COMMIT_COUNT"
echo "versionName:  $VERSION_NAME"
echo "versionCode:  $VERSION_CODE"

build_web

step "Syncing web export into the Android project"
pnpm --dir "$MOBILE_DIR" exec cap sync android

step "Gradle $GRADLE_TASK"
(cd "$ANDROID_DIR" && bash ./gradlew clean "$GRADLE_TASK" -PversionCode="$VERSION_CODE" -PversionName="$VERSION_NAME")

APK_SRC="$ANDROID_DIR/app/build/outputs/apk/$BUILD_TYPE/Humbee-SFA-$BUILD_TYPE.apk"
[[ -f "$APK_SRC" ]] || fail "expected APK not found at $APK_SRC"
mkdir -p "$MOBILE_DIR/dist"
APK_OUT="$MOBILE_DIR/dist/Humbee-SFA-$ENV_NAME-$VERSION_NAME-$VERSION_CODE-$BUILD_TYPE.apk"
cp "$APK_SRC" "$APK_OUT"

step "Done"
echo "APK: $APK_OUT"
echo "Install on a connected device or emulator:"
echo "  adb install -r \"$APK_OUT\""
