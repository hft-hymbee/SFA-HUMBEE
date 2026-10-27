#!/usr/bin/env bash
# Build the iOS app for one environment and run it on the iOS Simulator. No Apple account or signing needed.
#   Usage: scripts/run-ios-sim.sh <local|qa|prod> [simulator name]
# Simulator defaults to $HUMBEE_IOS_SIM, else "iPhone 17 Pro", else the first iPhone on the newest iOS runtime.
# First-time machine setup: see apps/mobile/BUILDING.md.
set -euo pipefail

source "$(dirname "${BASH_SOURCE[0]}")/lib/web-build.sh"
IOS_PROJECT="$MOBILE_DIR/ios/App/App.xcodeproj"
DERIVED_DATA="$MOBILE_DIR/ios/App/build"
BUNDLE_ID="com.humbee.sfa"

resolve_env "${1:-}" "$0 <local|qa|prod> [simulator name]"
SIM_NAME="${2:-${HUMBEE_IOS_SIM:-iPhone 17 Pro}}"

step "Preflight"
command -v xcodebuild >/dev/null || fail "xcodebuild not found. Install Xcode from the App Store. See BUILDING.md (iOS step 1)."
xcode-select -p | grep -q "Xcode.app" \
  || fail "Command-line tools point at $(xcode-select -p), not Xcode. Run: sudo xcode-select -s /Applications/Xcode.app"

# Pick a simulator on the newest installed iOS runtime (Xcode only builds for runtimes matching its SDK):
# the named device if it exists there, otherwise the first iPhone. Prints "<udid>\t<name>\t<runtime>".
pick_sim() {
  xcrun simctl list devices available -j | python3 -c '
import json, re, sys
want = sys.argv[1]
devices = json.load(sys.stdin)["devices"]
runtimes = sorted(
    (r for r in devices if ".SimRuntime.iOS-" in r and devices[r]),
    key=lambda r: [int(x) for x in re.findall(r"\d+", r.split("iOS-")[1])],
    reverse=True,
)
for runtime in runtimes:
    phones = [d for d in devices[runtime] if d["name"].startswith("iPhone")]
    if not phones:
        continue
    named = [d for d in phones if d["name"] == want]
    d = (named or phones)[0]
    print(d["udid"], d["name"], runtime.split("SimRuntime.")[1], sep="\t")
    break
' "$1"
}
SIM_LINE="$(pick_sim "$SIM_NAME")"
[[ -n "$SIM_LINE" ]] || fail "No iPhone simulators found. Add one in Xcode > Window > Devices and Simulators. See BUILDING.md (iOS step 1)."
IFS=$'\t' read -r SIM_UDID SIM_PICKED SIM_RUNTIME <<<"$SIM_LINE"
[[ "$SIM_PICKED" == "$SIM_NAME" ]] || warn "Simulator '$SIM_NAME' not found on the newest iOS runtime; using '$SIM_PICKED'."
echo "Xcode:        $(xcodebuild -version | head -n 1)"
echo "Simulator:    $SIM_PICKED ($SIM_RUNTIME, $SIM_UDID)"

load_env
echo "Version:      $APP_VERSION ($COMMIT_COUNT)"

build_web

step "Syncing web export into the iOS project"
pnpm --dir "$MOBILE_DIR" exec cap sync ios

step "Building for the simulator"
xcodebuild -project "$IOS_PROJECT" -scheme App -configuration Debug \
  -sdk iphonesimulator -destination "id=$SIM_UDID" \
  -derivedDataPath "$DERIVED_DATA" \
  MARKETING_VERSION="$APP_VERSION" CURRENT_PROJECT_VERSION="$COMMIT_COUNT" \
  CODE_SIGNING_ALLOWED=NO -quiet build
APP_PATH="$DERIVED_DATA/Build/Products/Debug-iphonesimulator/App.app"
[[ -d "$APP_PATH" ]] || fail "expected app not found at $APP_PATH"

step "Installing and launching"
xcrun simctl boot "$SIM_UDID" 2>/dev/null || true
open -a Simulator --args -CurrentDeviceUDID "$SIM_UDID"
xcrun simctl bootstatus "$SIM_UDID" -b >/dev/null
xcrun simctl terminate "$SIM_UDID" "$BUNDLE_ID" 2>/dev/null || true
xcrun simctl install "$SIM_UDID" "$APP_PATH"
xcrun simctl launch "$SIM_UDID" "$BUNDLE_ID" >/dev/null
# A freshly booted simulator can bring its home screen up over the app; relaunch once if that happened.
sleep 3
xcrun simctl spawn "$SIM_UDID" launchctl list | grep -q "$BUNDLE_ID" \
  || xcrun simctl launch "$SIM_UDID" "$BUNDLE_ID" >/dev/null

step "Done"
echo "Humbee SFA ($ENV_NAME) is running on the simulator."
echo "Inspect it: Safari > Develop > Simulator > localhost (enable Develop in Safari > Settings > Advanced)."
