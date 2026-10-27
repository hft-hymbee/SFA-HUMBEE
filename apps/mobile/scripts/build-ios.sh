#!/usr/bin/env bash
# Archive the iOS app for one environment and upload it to TestFlight (default) or export an .ipa.
#   Usage: scripts/build-ios.sh <local|qa|prod> [testflight|ipa]
# Needs: Apple ID signed in to Xcode, a team ID (DEVELOPMENT_TEAM in the project or $HUMBEE_IOS_TEAM_ID),
# and an App Store Connect app record for com.humbee.sfa. See apps/mobile/BUILDING.md (iOS).
set -euo pipefail

MODE="${2:-testflight}"

source "$(dirname "${BASH_SOURCE[0]}")/lib/web-build.sh"
IOS_DIR="$MOBILE_DIR/ios"
IOS_PROJECT="$IOS_DIR/App/App.xcodeproj"
EXPORT_OPTIONS="$IOS_DIR/ExportOptions-testflight.plist"

resolve_env "${1:-}" "$0 <local|qa|prod> [testflight|ipa]"
case "$MODE" in
  testflight) DESTINATION="upload" ;;
  ipa)        DESTINATION="export" ;;
  *) fail "mode must be 'testflight' or 'ipa', got '$MODE'" ;;
esac

step "Preflight"
command -v xcodebuild >/dev/null || fail "xcodebuild not found. Install Xcode from the App Store. See BUILDING.md (iOS step 1)."
xcode-select -p | grep -q "Xcode.app" \
  || fail "Command-line tools point at $(xcode-select -p), not Xcode. Run: sudo xcode-select -s /Applications/Xcode.app"

TEAM_ID="${HUMBEE_IOS_TEAM_ID:-$(grep -m 1 -oE 'DEVELOPMENT_TEAM = [A-Z0-9]{10};' "$IOS_PROJECT/project.pbxproj" | grep -oE '[A-Z0-9]{10}' || true)}"
[[ -n "$TEAM_ID" ]] \
  || fail "No Apple team ID. Set DEVELOPMENT_TEAM in the project or export HUMBEE_IOS_TEAM_ID=<10-char team id>. See BUILDING.md (iOS step 3)."
echo "Xcode:        $(xcodebuild -version | head -n 1)"
echo "Team ID:      $TEAM_ID"

load_env
# Build numbers must be unique per upload; QA and prod share one App Store Connect app, so add a timestamp.
BUILD_NUMBER="$COMMIT_COUNT.$(date +%y%m%d).$(date +%H%M)"
echo "Version:      $APP_VERSION ($BUILD_NUMBER)"

build_web

step "Syncing web export into the iOS project"
pnpm --dir "$MOBILE_DIR" exec cap sync ios

OUT_DIR="$MOBILE_DIR/dist/ios"
ARCHIVE="$OUT_DIR/Humbee-SFA-$ENV_NAME-$APP_VERSION-$BUILD_NUMBER.xcarchive"
mkdir -p "$OUT_DIR"

step "Archiving (Release)"
xcodebuild -project "$IOS_PROJECT" -scheme App -configuration Release \
  -destination "generic/platform=iOS" -archivePath "$ARCHIVE" \
  -allowProvisioningUpdates DEVELOPMENT_TEAM="$TEAM_ID" \
  MARKETING_VERSION="$APP_VERSION" CURRENT_PROJECT_VERSION="$BUILD_NUMBER" \
  -quiet archive

OPTIONS="$OUT_DIR/ExportOptions.plist"
cp "$EXPORT_OPTIONS" "$OPTIONS"
/usr/libexec/PlistBuddy -c "Set :destination $DESTINATION" "$OPTIONS"
/usr/libexec/PlistBuddy -c "Add :teamID string $TEAM_ID" "$OPTIONS"

EXPORT_DIR="$OUT_DIR/export-$ENV_NAME"
rm -rf "$EXPORT_DIR"
if [[ "$MODE" == "testflight" ]]; then
  step "Uploading to App Store Connect"
else
  step "Exporting .ipa"
fi
xcodebuild -exportArchive -archivePath "$ARCHIVE" -exportOptionsPlist "$OPTIONS" \
  -exportPath "$EXPORT_DIR" -allowProvisioningUpdates

step "Done"
if [[ "$MODE" == "testflight" ]]; then
  echo "Uploaded Humbee SFA $APP_VERSION ($BUILD_NUMBER) for $ENV_NAME."
  echo "Next, in App Store Connect > Humbee SFA > TestFlight:"
  echo "  1. Wait for the build to finish processing (usually 10-30 min; you get an email)."
  echo "  2. Set 'What to Test' to say this is the $(echo "$ENV_NAME" | tr '[:lower:]' '[:upper:]') build."
  echo "  3. Add it to your tester group."
else
  IPA_SRC="$(find "$EXPORT_DIR" -maxdepth 1 -name '*.ipa' | head -n 1)"
  [[ -n "$IPA_SRC" ]] || fail "no .ipa found in $EXPORT_DIR"
  IPA_OUT="$MOBILE_DIR/dist/Humbee-SFA-$ENV_NAME-$APP_VERSION-$BUILD_NUMBER.ipa"
  cp "$IPA_SRC" "$IPA_OUT"
  echo "IPA: $IPA_OUT"
  echo "Upload it with the Transporter app (Mac App Store) to send it to TestFlight."
fi
