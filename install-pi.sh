#!/usr/bin/env bash
# sets up a raspberry pi (64-bit raspberry pi os) for ytmp34:
#  - a proxy that oracle sends its youtube traffic through (see setup-oracle.sh)
#  - its own ytmp34 server as a slow backup, public through tailscale funnel
#   curl -fsSL https://raw.githubusercontent.com/rquw/ytmp34/main/install-pi.sh | bash
# safe to run again: it updates everything and keeps the settings
set -euo pipefail

D="$HOME/ytmp34"
PORT=8765
RAW="https://raw.githubusercontent.com/rquw/ytmp34/main"
MEM_MB=$(( $(grep MemTotal /proc/meminfo | awk '{print $2}') / 1024 ))
SLOTS=$(( MEM_MB < 1500 ? 1 : 2 ))

echo "==> Installing packages"
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-venv ffmpeg curl

# small pis (zero 2 w: 512 MB) need extra swap or a conversion can run out of memory
if [ "$MEM_MB" -lt 1500 ] && [ ! -f /swapfile ]; then
  echo "==> Adding 1 GB swap"
  sudo fallocate -l 1G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap -q /swapfile
  echo '/swapfile none swap sw,pri=10 0 0' | sudo tee -a /etc/fstab >/dev/null
  sudo swapon /swapfile
fi

echo "==> Installing ytmp34"
mkdir -p "$D/tmp"
curl -fsSL "$RAW/server.py" -o "$D/server.py"
[ -d "$D/venv" ] || python3 -m venv "$D/venv"
"$D/venv/bin/pip" install -q -U pip "yt-dlp[default]" deno

echo "==> Setting up the service"
# YTMP34_COOKIES is only used if cookies.txt exists. a home internet connection usually doesn't need it.
sudo tee /etc/systemd/system/ytmp34.service >/dev/null <<UNIT
[Unit]
Description=ytmp34 server
After=network-online.target
Wants=network-online.target

[Service]
User=$USER
Environment=YTMP34_COOKIES=$D/cookies.txt
Environment=YTMP34_MAX=$SLOTS
# /tmp is in RAM on raspberry pi os 13, too small for videos
Environment=TMPDIR=$D/tmp
Environment=PATH=$D/venv/bin:/usr/local/bin:/usr/bin:/bin
ExecStartPre=-$D/venv/bin/pip install -q -U "yt-dlp[default]" deno
ExecStart=$D/venv/bin/python $D/server.py --host 127.0.0.1 --port $PORT
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

# restart every night at 4 so yt-dlp stays up to date
sudo tee /etc/systemd/system/ytmp34-update.service >/dev/null <<UNIT
[Service]
Type=oneshot
ExecStart=/bin/systemctl restart ytmp34
UNIT
sudo tee /etc/systemd/system/ytmp34-update.timer >/dev/null <<UNIT
[Timer]
OnCalendar=*-*-* 04:00
Persistent=true

[Install]
WantedBy=timers.target
UNIT
sudo systemctl daemon-reload
sudo systemctl enable -q ytmp34 ytmp34-update.timer
sudo systemctl restart ytmp34 ytmp34-update.timer

echo "==> Setting up Tailscale Funnel (public https address, no port forwarding)"
command -v tailscale >/dev/null || curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale status >/dev/null 2>&1 || sudo tailscale up
sudo tailscale funnel --bg "$PORT"

echo "==> Setting up the proxy for Oracle (only reachable over Tailscale)"
# oracle converts, but sends its youtube traffic through here so youtube sees a home connection
sudo apt-get install -y -qq microsocks
sudo tee /etc/systemd/system/ytmp34-proxy.service >/dev/null <<'UNIT'
[Unit]
Description=SOCKS proxy for ytmp34 on Oracle (tailscale only)
After=tailscaled.service network-online.target
Wants=tailscaled.service

[Service]
DynamicUser=yes
ExecStart=/bin/sh -c "exec /usr/bin/microsocks -i $(tailscale ip -4) -p 1080"
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT
sudo systemctl daemon-reload
sudo systemctl enable -q ytmp34-proxy
sudo systemctl restart ytmp34-proxy

for _ in $(seq 30); do curl -fsS "http://127.0.0.1:$PORT/ping" >/dev/null 2>&1 && break; sleep 2; done
HOST="$(tailscale status --json | python3 -c 'import json,sys; print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))')"
echo
echo "ytmp34 (slow backup) is at https://$HOST"
echo "Proxy for Oracle:          socks5h://$(tailscale ip -4):1080"
echo "Set up Oracle with:        ssh ubuntu@<oracle-ip> 'PI_PROXY=socks5h://$(tailscale ip -4):1080 bash -s' < setup-oracle.sh"
