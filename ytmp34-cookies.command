#!/bin/bash
# double-click to refresh the server's youtube cookies.
# uses its own chrome window (separate from your normal chrome) where the spare account stays signed in.
set -uo pipefail

DIR="$HOME/.ytmp34"
PROFILE="$DIR/chrome"
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
KEY="$HOME/Downloads/ssh-key-2026-10-22.key"
VM=ubuntu@132.226.199.122
SITE=https://132-226-199-122.sslip.io
VIDEO="https://www.youtube.com/watch?v=jNQXAC9IVRw"

mkdir -p "$DIR"
if [ ! -x "$DIR/venv/bin/yt-dlp" ]; then
  echo "First time: installing yt-dlp…"
  python3 -m venv "$DIR/venv" && "$DIR/venv/bin/pip" install -q -U yt-dlp || { echo "Couldn't install yt-dlp."; exit 1; }
fi

open_chrome() {
  "$CHROME" --user-data-dir="$PROFILE" --no-first-run --no-default-browser-check "$1" >/dev/null 2>&1 &
  CHROME_PID=$!
}
close_chrome() {
  kill -TERM "$CHROME_PID" 2>/dev/null
  while kill -0 "$CHROME_PID" 2>/dev/null; do sleep 0.5; done
}
grab_cookies() {
  rm -f "$DIR/cookies.txt"
  "$DIR/venv/bin/yt-dlp" -q --no-warnings --skip-download --cookies-from-browser "chrome:$PROFILE/Default" \
    --cookies "$DIR/cookies.txt" "$VIDEO" >/dev/null 2>&1
  grep -q $'\tSAPISID\t' "$DIR/cookies.txt" 2>/dev/null && grep -q $'\tLOGIN_INFO\t' "$DIR/cookies.txt"
}

echo "Opening YouTube in the ytmp34 Chrome window…"
open_chrome "$VIDEO"
sleep 15
close_chrome

if ! grab_cookies; then
  echo
  echo "The spare account isn't signed in there (first time, or Google signed it out)."
  echo "A Chrome window opens now: sign in to YouTube with the spare account."
  echo "Decline any extra prompts (passkey, recovery info, …)."
  open_chrome "https://accounts.google.com/ServiceLogin?service=youtube&continue=https%3A%2F%2Fwww.youtube.com%2F"
  read -r -p "When YouTube shows you signed in, come back here and press Enter… "
  close_chrome
  open_chrome "$VIDEO"
  sleep 10
  close_chrome
  grab_cookies || { echo "Still not signed in. Double-click again to retry."; read -r -p "Press Enter to close."; exit 1; }
fi

echo "Uploading the cookies…"
scp -q -i "$KEY" "$DIR/cookies.txt" $VM:ytmp34/cookies.new &&
  ssh -i "$KEY" $VM 'chmod 600 ~/ytmp34/cookies.new && mv ~/ytmp34/cookies.new ~/ytmp34/cookies.txt' ||
  { echo "Couldn't reach the server."; read -r -p "Press Enter to close."; exit 1; }
rm -f "$DIR/cookies.txt"

echo "Testing a download…"
OUT=$(mktemp)
CODE=$(curl -s -o "$OUT" -w "%{http_code}" --max-time 180 "$SITE/dl?fmt=mp3&url=https%3A%2F%2Fyoutu.be%2FjNQXAC9IVRw")
if [ "$CODE" = "200" ]; then
  echo "✓ ytmp34 is working again."
else
  echo "✗ Still not working: $(cat "$OUT")"
fi
rm -f "$OUT"
read -r -p "Press Enter to close."
