#!/usr/bin/env bash
# uploads the newest cookies export from Downloads to the server and checks it works
#   curl -fsSL https://raw.githubusercontent.com/rquw/ytmp34/main/refresh-cookies.sh | bash
set -euo pipefail

KEY=~/Downloads/ssh-key-2026-10-22.key
VM=ubuntu@132.226.199.122
SITE=https://132-226-199-122.sslip.io

FILE=$(ls -t ~/Downloads/*cookies*.txt 2>/dev/null | head -1 || true)
if [ -z "$FILE" ]; then
  echo "No cookies file in Downloads. Export one first (Incognito, Get cookies.txt LOCALLY, Export)."
  exit 1
fi
if ! head -1 "$FILE" | grep -q "Netscape HTTP Cookie File" || ! grep -q "youtube.com" "$FILE"; then
  echo "$(basename "$FILE") doesn't look like a YouTube cookies export. Export it again in Netscape format."
  exit 1
fi

echo "Uploading $(basename "$FILE")…"
scp -q -i $KEY "$FILE" $VM:ytmp34/cookies.new
ssh -i $KEY $VM 'chmod 600 ~/ytmp34/cookies.new && mv ~/ytmp34/cookies.new ~/ytmp34/cookies.txt'

echo "Testing a download…"
OUT=$(mktemp)
CODE=$(curl -s -o "$OUT" -w "%{http_code}" --max-time 180 "$SITE/dl?fmt=mp3&url=https%3A%2F%2Fyoutu.be%2FjNQXAC9IVRw")
if [ "$CODE" = "200" ]; then
  echo "✓ ytmp34 is working again. You can delete $(basename "$FILE") from Downloads now."
else
  echo "✗ Still not working: $(cat "$OUT")"
  echo "  Try exporting the cookies again (and close the Incognito window right after)."
fi
rm -f "$OUT"
