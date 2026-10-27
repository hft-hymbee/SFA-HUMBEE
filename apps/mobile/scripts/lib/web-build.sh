# Shared by build-android.sh, run-ios-sim.sh and build-ios.sh. Source it; don't run it.
# Provides: MOBILE_DIR, REPO_ROOT, WEB_DIR, fail/warn/step, resolve_env, load_env, build_web.

MOBILE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
REPO_ROOT="$(cd "$MOBILE_DIR/../.." && pwd)"
WEB_DIR="$REPO_ROOT/apps/web"

fail() { echo "ERROR: $*" >&2; exit 1; }
warn() { echo "WARNING: $*" >&2; }
step() { echo; echo "==> $*"; }

# resolve_env <env> <usage>: sets ENV_NAME, ENV_FILE and WEB_SCRIPT (the apps/web build script for that env).
resolve_env() {
  ENV_NAME="$1"
  case "$ENV_NAME" in
    local) ENV_FILE="$WEB_DIR/.env.local"; WEB_SCRIPT="build" ;;
    qa)    ENV_FILE="$WEB_DIR/.env.qa";    WEB_SCRIPT="build:qa" ;;
    prod)  ENV_FILE="$WEB_DIR/.env.prod";  WEB_SCRIPT="build:prod" ;;
    *) fail "usage: $2" ;;
  esac
}

read_env() { grep -E "^$1=" "$ENV_FILE" | tail -n 1 | cut -d= -f2- | sed -e 's/^["'\'']//' -e 's/["'\'']$//'; }

# load_env: reads API_URL and APP_VERSION from ENV_FILE, sets COMMIT_COUNT, and rejects non-https API URLs.
load_env() {
  step "Environment: $ENV_NAME ($ENV_FILE)"
  [[ -f "$ENV_FILE" ]] || fail "$ENV_FILE not found"
  API_URL="$(read_env NEXT_PUBLIC_SFA_API_BASE_URL)"
  APP_VERSION="$(read_env NEXT_PUBLIC_APP_VERSION)"
  APP_VERSION="${APP_VERSION:-1.0.0}"
  COMMIT_COUNT="$(git -C "$REPO_ROOT" rev-list --count HEAD)"

  [[ -n "$API_URL" ]] || fail "NEXT_PUBLIC_SFA_API_BASE_URL is not set in $ENV_FILE"
  if [[ "$API_URL" != https://* ]]; then
    fail "API URL for '$ENV_NAME' is '$API_URL'. The app only allows https (Android blocks cleartext traffic and mixed content; iOS App Transport Security blocks http), so every API call would fail. Switch the URL to https."
  fi
  if [[ "$API_URL" == *localhost* || "$API_URL" == *127.0.0.1* ]]; then
    warn "API URL points at localhost. On a phone, emulator or simulator that may not be your API, so API calls can fail. Use your Mac's LAN address or a tunnel."
  fi
  echo "API URL:      $API_URL"
}

# build_web: builds apps/web/out for ENV_NAME and checks the env's API URL is the one baked in.
build_web() {
  step "Building web export (pnpm --dir apps/web $WEB_SCRIPT)"
  rm -rf "$WEB_DIR/out"
  pnpm --dir "$WEB_DIR" "$WEB_SCRIPT"
  [[ -f "$WEB_DIR/out/index.html" ]] || fail "web build did not produce apps/web/out/index.html"
  # Next.js also auto-loads .env.local; make sure this env's API URL is the one baked into the bundle.
  grep -rqF "${API_URL%/}" "$WEB_DIR/out/_next/static" \
    || fail "web export does not contain $API_URL. Another env file (e.g. .env.local) may have overridden $ENV_FILE."
  echo "Verified: web export calls $API_URL"
}
