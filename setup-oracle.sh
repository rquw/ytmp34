#!/usr/bin/env bash
# sets up the main ytmp34 server on an oracle cloud vm (ubuntu, always free).
# it does the converting; its youtube traffic goes through the home pi (install-pi.sh prints PI_PROXY),
# so youtube sees a home connection and no cookies are needed.
#   ssh ubuntu@<ip> 'PI_PROXY=socks5h://100.x.y.z:1080 bash -s' < setup-oracle.sh
# safe to run again. also open ports 80 and 443 in the vm's security list in the oracle console.
set -euo pipefail

: "${PI_PROXY:?set PI_PROXY to the address install-pi.sh printed, e.g. socks5h://100.x.y.z:1080}"
D=$HOME/ytmp34
RAW="https://raw.githubusercontent.com/rquw/ytmp34/main"
IP=$(curl -fsS https://ifconfig.me)
HOST="${IP//./-}.sslip.io"

echo "==> Installing packages"
sudo apt-get update -qq
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3 python3-venv ffmpeg curl caddy iptables-persistent

echo "==> Installing ytmp34"
mkdir -p "$D"
curl -fsSL "$RAW/server.py" -o "$D/server.py"
[ -d "$D/venv" ] || python3 -m venv "$D/venv"
"$D/venv/bin/pip" install -q -U pip "yt-dlp[default]" deno

echo "==> Joining Tailscale (open the link it prints if it asks you to log in)"
command -v tailscale >/dev/null || curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale status >/dev/null 2>&1 || sudo tailscale up --hostname=ytmp34-oracle
PROXY_HOST=$(echo "$PI_PROXY" | sed -E 's#^[a-z0-9]+://##; s#:[0-9]+$##')
PROXY_PORT=${PI_PROXY##*:}
if ! timeout 10 bash -c "</dev/tcp/$PROXY_HOST/$PROXY_PORT" 2>/dev/null; then
  echo "Can't reach the pi's proxy at $PI_PROXY. Is the pi on and in the same tailnet?"
  exit 1
fi

echo "==> Setting up the service"
sudo tee /etc/systemd/system/ytmp34.service >/dev/null <<UNIT
[Unit]
Description=ytmp34 server
After=network-online.target tailscaled.service
Wants=network-online.target

[Service]
User=$USER
Environment=YTMP34_MAX=2
Environment=YTMP34_PROXY=$PI_PROXY
Environment=PATH=$D/venv/bin:/usr/local/bin:/usr/bin:/bin
ExecStartPre=-$D/venv/bin/pip install -q -U "yt-dlp[default]" deno
ExecStart=$D/venv/bin/python $D/server.py --host 127.0.0.1 --port 8765
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

echo "==> Opening ports 80/443 and setting up https"
# oracle's ubuntu image rejects everything not explicitly allowed
REJ=$(sudo iptables -S INPUT | grep -n -- '-j REJECT' | head -1 | cut -d: -f1 || true)
POS=()
[ -n "$REJ" ] && POS=($((REJ - 1)))  # line 1 of -S is the policy, so rule number = line - 1
for p in 443 80; do
  sudo iptables -C INPUT -p tcp -m state --state NEW -m tcp --dport $p -j ACCEPT 2>/dev/null ||
    sudo iptables -I INPUT "${POS[@]}" -p tcp -m state --state NEW -m tcp --dport $p -j ACCEPT
done
sudo sh -c 'iptables-save > /etc/iptables/rules.v4'
printf '%s {\n\treverse_proxy 127.0.0.1:8765\n}\n' "$HOST" | sudo tee /etc/caddy/Caddyfile >/dev/null
sudo systemctl restart caddy

for _ in $(seq 60); do curl -fsS http://127.0.0.1:8765/ping >/dev/null 2>&1 && break; sleep 2; done
echo
echo "ytmp34 is at https://$HOST"
echo "Put that address in index.html (const SERVER) if it changed."
