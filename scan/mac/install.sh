#!/usr/bin/env bash
# builds PRISMO scan, puts it in ~/Applications and starts it at login.
#   bash install.sh            (asks for the scan key the first time)
#   bash install.sh uninstall
set -euo pipefail
cd "$(dirname "$0")"

APP="$HOME/Applications/PRISMO Scan.app"
AGENT="$HOME/Library/LaunchAgents/at.fabiosch.prismoscan.plist"
KEY="$HOME/.config/prismo-scan/key"

launchctl bootout "gui/$(id -u)" "$AGENT" 2>/dev/null || true
if [ "${1:-}" = "uninstall" ]; then
  rm -rf "$APP" "$AGENT"
  echo "PRISMO scan removed (key kept in $KEY)"
  exit 0
fi

command -v swiftc >/dev/null || { echo "needs the Xcode command line tools: xcode-select --install"; exit 1; }

if [ ! -s "$KEY" ]; then
  read -rp "scan key (install-pi.sh printed it): " k
  mkdir -p "$(dirname "$KEY")"
  (umask 077; printf '%s' "$k" > "$KEY")
fi

echo "==> building"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS"
swiftc -O -o "$APP/Contents/MacOS/PrismoScan" PrismoScan.swift -framework Cocoa
cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleIdentifier</key><string>at.fabiosch.prismoscan</string>
  <key>CFBundleName</key><string>PRISMO Scan</string>
  <key>CFBundleExecutable</key><string>PrismoScan</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>LSMinimumSystemVersion</key><string>11.0</string>
  <key>LSUIElement</key><true/>
</dict></plist>
PLIST
codesign --force -s - "$APP" >/dev/null 2>&1 || true

echo "==> start at login"
mkdir -p "$(dirname "$AGENT")"
cat > "$AGENT" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>at.fabiosch.prismoscan</string>
  <key>ProgramArguments</key><array><string>$APP/Contents/MacOS/PrismoScan</string></array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><dict><key>SuccessfulExit</key><false/></dict>
</dict></plist>
PLIST
launchctl bootstrap "gui/$(id -u)" "$AGENT"
echo "PRISMO scan is running (look for the QR icon in the menu bar)"
