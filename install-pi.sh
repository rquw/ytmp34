#!/usr/bin/env bash
# ytmp34 server installer for Raspberry Pi OS / Debian.
#   curl -fsSL https://raw.githubusercontent.com/rquw/ytmp34/main/install-pi.sh | bash
# Re-running is safe: it updates the code and keeps your key.
set -euo pipefail

DIR="$HOME/ytmp34"
PORT=8765
RAW="https://raw.githubusercontent.com/rquw/ytmp34/main"

echo "==> Installing packages"
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-venv ffmpeg curl

mkdir -p "$DIR"
curl -fsSL "$RAW/server.py" -o "$DIR/server.py"
[ -d "$DIR/venv" ] || python3 -m venv "$DIR/venv"
"$DIR/venv/bin/pip" install -q -U pip yt-dlp

# Secret key so only you can use your Pi (kept across re-installs).
[ -f "$DIR/key" ] || head -c 18 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' > "$DIR/key"
KEY="$(cat "$DIR/key")"

echo "==> Setting up service"
sudo tee /etc/systemd/system/ytmp34.service >/dev/null <<EOF
[Unit]
Description=ytmp34 server
After=network-online.target
Wants=network-online.target

[Service]
User=$USER
Environment=YTMP34_KEY=$KEY
ExecStartPre=-$DIR/venv/bin/pip install -q -U yt-dlp
ExecStart=$DIR/venv/bin/python $DIR/server.py --port $PORT
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# YouTube changes often; restart nightly so yt-dlp updates itself (ExecStartPre).
sudo tee /etc/systemd/system/ytmp34-update.service >/dev/null <<EOF
[Service]
Type=oneshot
ExecStart=/bin/systemctl restart ytmp34
EOF
sudo tee /etc/systemd/system/ytmp34-update.timer >/dev/null <<EOF
[Timer]
OnCalendar=*-*-* 04:00
Persistent=true

[Install]
WantedBy=timers.target
EOF
sudo systemctl daemon-reload
sudo systemctl enable --now ytmp34 ytmp34-update.timer
sudo systemctl restart ytmp34

echo "==> Setting up Tailscale Funnel (public HTTPS address)"
command -v tailscale >/dev/null || curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale status >/dev/null 2>&1 || sudo tailscale up
sudo tailscale funnel --bg "$PORT"

HOST="$(tailscale status --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))')"
echo
echo "=================================================================="
echo " Done. Open this link once on each phone/PC (it saves the settings):"
echo
echo "   https://rquw.github.io/ytmp34/#s=https://$HOST&k=$KEY"
echo "=================================================================="
