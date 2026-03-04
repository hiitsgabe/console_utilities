#!/usr/bin/env bash
#
# Android Emulator management for Console Utilities
# Uses budtmo/docker-android with noVNC for browser-based interaction
#
set -euo pipefail

EMULATOR_IMAGE="budtmo/docker-android:emulator_11.0"
CONTAINER_NAME="console-utils-android"
VNC_PORT="${EMULATOR_VNC_PORT:-6080}"
PACKAGE="com.consoleutilities.consoleutilities"
ACTIVITY="org.kivy.android.PythonActivity"
BOOT_TIMEOUT=180  # seconds

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

log()  { echo -e "${GREEN}✅ $*${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $*${NC}"; }
err()  { echo -e "${RED}❌ $*${NC}" >&2; }

# ── Helpers ──────────────────────────────────────────────────────────────────

is_running() {
  docker ps -q -f name="^${CONTAINER_NAME}$" 2>/dev/null | grep -q .
}

is_booted() {
  local boot
  boot=$(docker exec "$CONTAINER_NAME" adb -s emulator-5554 shell getprop sys.boot_completed 2>/dev/null | tr -d '\r\n')
  [ "$boot" = "1" ]
}

wait_for_device() {
  echo -n "⏳ Waiting for emulator device"
  local elapsed=0
  while ! docker exec "$CONTAINER_NAME" adb devices 2>/dev/null | grep -q 'emulator-5554'; do
    sleep 3; elapsed=$((elapsed + 3))
    echo -n "."
    if [ $elapsed -ge $BOOT_TIMEOUT ]; then
      echo ""
      err "Timed out waiting for emulator device"
      exit 1
    fi
  done
  echo " found!"
}

wait_for_boot() {
  echo -n "⏳ Waiting for Android to boot (first boot takes ~2-3 min)"
  local elapsed=0
  while ! is_booted; do
    sleep 5; elapsed=$((elapsed + 5))
    echo -n "."
    if [ $elapsed -ge $BOOT_TIMEOUT ]; then
      echo ""
      err "Timed out waiting for Android boot after ${BOOT_TIMEOUT}s"
      err "Check logs: docker logs $CONTAINER_NAME"
      exit 1
    fi
  done
  echo " booted!"
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

cmd_start() {
  if is_running; then
    log "Emulator already running"
  else
    # Check KVM
    if [ ! -e /dev/kvm ]; then
      err "KVM not available. Android emulator requires hardware virtualization."
      exit 1
    fi

    # Clean up old container
    docker rm -f "$CONTAINER_NAME" 2>/dev/null || true

    echo "🤖 Starting Android emulator (Android 11, Galaxy S10)..."
    docker run -d \
      --name "$CONTAINER_NAME" \
      --device /dev/kvm \
      -p "${VNC_PORT}:6080" \
      -e EMULATOR_DEVICE="Samsung Galaxy S10" \
      -e WEB_VNC=true \
      -e EMULATOR_ADDITIONAL_ARGS="-no-snapshot" \
      --tmpfs /home/androidusr/emulator:rw,exec,size=8g,uid=1300,gid=1301 \
      "$EMULATOR_IMAGE" > /dev/null

    log "Container started"
  fi

  wait_for_device
  wait_for_boot
  log "Android emulator is ready"
}

cmd_install() {
  if ! is_running; then
    err "Emulator not running. Run: make run-android"
    exit 1
  fi

  local apk
  apk=$(find_apk "${1:-dist}")
  echo "📱 Installing: $(basename "$apk")"

  docker cp "$apk" "${CONTAINER_NAME}:/tmp/console_utils.apk"

  # Uninstall old version if present
  docker exec "$CONTAINER_NAME" adb -s emulator-5554 uninstall "$PACKAGE" 2>/dev/null || true

  docker exec "$CONTAINER_NAME" adb -s emulator-5554 install /tmp/console_utils.apk
  log "APK installed"
}

cmd_launch() {
  if ! is_running; then
    err "Emulator not running. Run: make run-android"
    exit 1
  fi

  echo "🚀 Launching Console Utilities..."
  docker exec "$CONTAINER_NAME" adb -s emulator-5554 shell am start \
    -n "${PACKAGE}/${ACTIVITY}" > /dev/null
  log "App launched"
}

cmd_run() {
  cmd_start
  cmd_install "${1:-dist}"
  cmd_launch

  echo ""
  log "Console Utilities running on Android emulator!"
  echo "   📺 Open in browser: http://localhost:${VNC_PORT}/"
  echo "   📺 Or via exe.dev:  https://$(hostname).exe.xyz:${VNC_PORT}/"
  echo "   Click 'Connect' in the noVNC page to interact."
  echo ""
}

cmd_stop() {
  echo "🛑 Stopping Android emulator..."
  docker rm -f "$CONTAINER_NAME" 2>/dev/null || true
  log "Emulator stopped"
}

cmd_status() {
  if is_running; then
    if is_booted; then
      log "Emulator running and booted (port $VNC_PORT)"
    else
      warn "Emulator running but still booting..."
    fi
  else
    echo "⚪ Emulator not running"
  fi
}

cmd_clean_emulator() {
  echo "🧹 Cleaning emulator Docker resources..."
  docker rm -f "$CONTAINER_NAME" 2>/dev/null || true
  docker rmi "$EMULATOR_IMAGE" 2>/dev/null || true
  docker system prune -f > /dev/null 2>&1
  log "Emulator Docker resources cleaned"
  df -h / | tail -1 | awk '{print "   Disk: " $4 " free of " $2}'
}

cmd_clean_build() {
  echo "🧹 Cleaning Android build Docker resources..."
  docker rm -f rom-build 2>/dev/null || true
  docker rmi rom-builder 2>/dev/null || true
  docker system prune -f > /dev/null 2>&1
  log "Build Docker resources cleaned"
  df -h / | tail -1 | awk '{print "   Disk: " $4 " free of " $2}'
}

cmd_clean_all() {
  cmd_stop 2>/dev/null || true
  echo "🧹 Cleaning ALL Docker resources..."
  docker rm -f rom-build "$CONTAINER_NAME" 2>/dev/null || true
  docker system prune -af --volumes > /dev/null 2>&1
  log "All Docker resources cleaned"
  df -h / | tail -1 | awk '{print "   Disk: " $4 " free of " $2}'
}

# ── Main ─────────────────────────────────────────────────────────────────────

case "${1:-help}" in
  start)          cmd_start ;;
  install)        cmd_install "${2:-dist}" ;;
  launch)         cmd_launch ;;
  run)            cmd_run "${2:-dist}" ;;
  stop)           cmd_stop ;;
  status)         cmd_status ;;
  clean-emulator) cmd_clean_emulator ;;
  clean-build)    cmd_clean_build ;;
  clean-all)      cmd_clean_all ;;
  help|*)
    echo "Usage: $0 <command>"
    echo ""
    echo "Commands:"
    echo "  run             Start emulator, install APK, and launch app"
    echo "  start           Start emulator only (no APK install)"
    echo "  install [dir]   Find and install APK from dist/ (or given dir)"
    echo "  launch          Launch the app (must be installed)"
    echo "  stop            Stop and remove the emulator container"
    echo "  status          Show emulator status"
    echo "  clean-emulator  Remove emulator container and image"
    echo "  clean-build     Remove Android build container and image"
    echo "  clean-all       Remove ALL Docker resources (emulator + build)"
    ;;
esac
