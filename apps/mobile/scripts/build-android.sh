#!/usr/bin/env bash
# Build an Android APK for one environment.
#   Usage: scripts/build-android.sh <local|qa|prod> [debug|release]
# Output: apps/mobile/dist/Humbee-SFA-<env>-<versionName>-<versionCode>-<type>.apk
# First-time machine setup: see apps/mobile/BUILDING.md.
set -euo pipefail

ENV_NAME="${1:-}"
BUILD_TYPE="${2:-debug}"

MOBILE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$MOBILE_DIR/../.." && pwd)"
WEB_DIR="$REPO_ROOT/apps/web"
ANDROID_DIR="$MOBILE_DIR/android"
STUDIO_JBR="/Applications/Android Studio.app/Contents/jbr/Contents/Home"
COMPILE_SDK=36

fail() { echo "ERROR: $*" >&2; exit 1; }
warn() { echo "WARNING: $*" >&2; }
step() { echo; echo "==> $*"; }

case "$ENV_NAME" in
  local) ENV_FILE="$WEB_DIR/.env.local"; WEB_SCRIPT="build" ;;
  qa)    ENV_FILE="$WEB_DIR/.env.qa";    WEB_SCRIPT="build:qa" ;;
  prod)  ENV_FILE="$WEB_DIR/.env.prod";  WEB_SCRIPT="build:prod" ;;
  *) fail "usage: $0 <local|qa|prod> [debug|release]" ;;
esac
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

step "Environment: $ENV_NAME ($ENV_FILE)"
[[ -f "$ENV_FILE" ]] || fail "$ENV_FILE not found"
read_env() { grep -E "^$1=" "$ENV_FILE" | tail -n 1 | cut -d= -f2- | sed -e 's/^["'\'']//' -e 's/["'\'']$//'; }
API_URL="$(read_env NEXT_PUBLIC_SFA_API_BASE_URL)"
VERSION_NAME="$(read_env NEXT_PUBLIC_APP_VERSION)"
VERSION_NAME="${VERSION_NAME:-1.0.0}"
VERSION_CODE="$(git -C "$REPO_ROOT" rev-list --count HEAD)"

[[ -n "$API_URL" ]] || fail "NEXT_PUBLIC_SFA_API_BASE_URL is not set in $ENV_FILE"
if [[ "$API_URL" != https://* ]]; then
  fail "API URL for '$ENV_NAME' is '$API_URL'. The Android app only allows https (cleartext traffic and mixed content are disabled), so every API call would fail. Switch the URL to https."
fi
if [[ "$API_URL" == *localhost* || "$API_URL" == *127.0.0.1* ]]; then
  warn "API URL points at localhost. On a phone or emulator that is the device itself, so API calls will fail. Use your Mac's LAN address or a tunnel."
fi
echo "API URL:      $API_URL"
echo "versionName:  $VERSION_NAME"
echo "versionCode:  $VERSION_CODE"

step "Building web export (pnpm --dir apps/web $WEB_SCRIPT)"
rm -rf "$WEB_DIR/out"
pnpm --dir "$WEB_DIR" "$WEB_SCRIPT"
[[ -f "$WEB_DIR/out/index.html" ]] || fail "web build did not produce apps/web/out/index.html"
# Next.js also auto-loads .env.local; make sure this env's API URL is the one baked into the bundle.
grep -rqF "${API_URL%/}" "$WEB_DIR/out/_next/static" \
  || fail "web export does not contain $API_URL. Another env file (e.g. .env.local) may have overridden $ENV_FILE."
echo "Verified: web export calls $API_URL"

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
