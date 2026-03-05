#!/usr/bin/env bash
#
# Appetize.io cloud emulator for Console Utilities
# Upload APK and get a browser link — no local emulator needed
#
set -euo pipefail

APPETIZE_API="https://api.appetize.io/v1/apps"
KEY_FILE=".appetize_key"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

log()  { echo -e "${GREEN}✅ $*${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $*${NC}"; }
err()  { echo -e "${RED}❌ $*${NC}" >&2; }

require_api_key() {
  if [ -z "${APPETIZE_API_KEY:-}" ]; then
    err "APPETIZE_API_KEY not set. Add it to .env or export it."
    exit 1
  fi
}

find_apk() {
  local dist_dir="${1:-dist}"

  # 1) Direct APK in dist/android/
  local apk
  apk=$(find "$dist_dir/android" -name '*.apk' 2>/dev/null | head -1)
  if [ -n "$apk" ]; then
    echo "$apk"
    return 0
  fi

  # 2) android.zip in dist/
  if [ -f "$dist_dir/android.zip" ]; then
    echo "📦 Extracting android.zip..." >&2
    rm -rf "$dist_dir/android"
    mkdir -p "$dist_dir/android"
    unzip -o "$dist_dir/android.zip" -d "$dist_dir/android" >&2
    apk=$(find "$dist_dir/android" -name '*.apk' 2>/dev/null | head -1)
    if [ -n "$apk" ]; then
      echo "$apk"
      return 0
    fi
  fi

  # 3) Download latest release from GitHub
  local repo_url
  repo_url=$(git remote get-url origin 2>/dev/null | sed 's/git@github.com:/https:\/\/github.com\//' | sed 's/\.git$//')
  if [ -n "$repo_url" ]; then
    local api_url="https://api.github.com/repos/$(echo "$repo_url" | sed 's|https://github.com/||')/releases/latest"
    local download_url
    download_url=$(curl -sL "$api_url" | grep -o '"browser_download_url": *"[^"]*android.zip"' | grep -o 'https://[^"]*')
    if [ -n "$download_url" ]; then
      warn "No local APK found. Downloading latest release..." >&2
      mkdir -p "$dist_dir/android"
      curl -sL -o "$dist_dir/android.zip" "$download_url"
      unzip -o "$dist_dir/android.zip" -d "$dist_dir/android" >&2
      apk=$(find "$dist_dir/android" -name '*.apk' 2>/dev/null | head -1)
      if [ -n "$apk" ]; then
        echo "$apk"
        return 0
      fi
    fi
  fi

  err "No APK found in $dist_dir/android/ or android.zip"
  return 1
}

# ── Commands ─────────────────────────────────────────────────────────────────

cmd_upload() {
  require_api_key

  local apk
  apk=$(find_apk "${1:-dist}")
  echo "📱 Uploading: $(basename "$apk")"

  local public_key=""
  local url="$APPETIZE_API"

  # Update existing app if we have a key
  if [ -f "$KEY_FILE" ]; then
    public_key=$(cat "$KEY_FILE")
    url="${APPETIZE_API}/${public_key}"
    echo "🔄 Updating existing app ($public_key)..."
  else
    echo "🆕 Creating new app on Appetize.io..."
  fi

  local response
  response=$(curl -sS "$url" \
    -u "${APPETIZE_API_KEY}:" \
    -F "file=@${apk}" \
    -F "platform=android")

  # Check for errors
  if echo "$response" | grep -q '"error"'; then
    err "Upload failed: $response"
    exit 1
  fi

  # Extract and save public key
  public_key=$(echo "$response" | grep -o '"publicKey":"[^"]*"' | cut -d'"' -f4)
  if [ -z "$public_key" ]; then
    err "Could not parse response: $response"
    exit 1
  fi

  echo "$public_key" > "$KEY_FILE"

  echo ""
  log "APK uploaded successfully!"
  echo "   🌐 Open in browser: https://appetize.io/app/${public_key}"
  echo ""
}

cmd_status() {
  require_api_key

  if [ ! -f "$KEY_FILE" ]; then
    echo "⚪ No app uploaded yet (no $KEY_FILE found)"
    return 0
  fi

  local public_key
  public_key=$(cat "$KEY_FILE")

  local response
  response=$(curl -sS "${APPETIZE_API}/${public_key}" \
    -u "${APPETIZE_API_KEY}:")

  if echo "$response" | grep -q '"publicKey"'; then
    log "App exists on Appetize.io"
    echo "   🔑 Public key: $public_key"
    echo "   🌐 Link: https://appetize.io/app/${public_key}"
  else
    warn "App not found on Appetize.io (may have been deleted)"
    echo "   Response: $response"
  fi
}

cmd_delete() {
  require_api_key

  if [ ! -f "$KEY_FILE" ]; then
    warn "No app to delete (no $KEY_FILE found)"
    return 0
  fi

  local public_key
  public_key=$(cat "$KEY_FILE")

  echo "🗑️  Deleting app $public_key from Appetize.io..."
  local http_code
  http_code=$(curl -sS -o /dev/null -w "%{http_code}" \
    -X DELETE "${APPETIZE_API}/${public_key}" \
    -u "${APPETIZE_API_KEY}:")

  if [ "$http_code" = "200" ] || [ "$http_code" = "204" ]; then
    rm -f "$KEY_FILE"
    log "App deleted from Appetize.io"
  else
    err "Delete failed (HTTP $http_code)"
    exit 1
  fi
}

# ── Main ─────────────────────────────────────────────────────────────────────

case "${1:-help}" in
  upload)  cmd_upload "${2:-dist}" ;;
  status)  cmd_status ;;
  delete)  cmd_delete ;;
  help|*)
    echo "Usage: $0 <command>"
    echo ""
    echo "Commands:"
    echo "  upload [dir]  Upload APK to Appetize.io (finds APK in dist/ or given dir)"
    echo "  status        Check if app exists on Appetize.io"
    echo "  delete        Remove app from Appetize.io"
    ;;
esac
