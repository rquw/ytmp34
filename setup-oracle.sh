#!/usr/bin/env bash
# ssh ubuntu@<ip> 'bash -s' < setup-oracle.sh
set -euo pipefail

D=$HOME/ytmp34
KEY=$(cat "$D/key")
IP=$(curl -fsS https://ifconfig.me)
HOST="${IP//./-}.sslip.io"

sudo tee /etc/systemd/system/ytmp34.service >/dev/null <<UNIT
[Unit]
Description=ytmp34 server
After=network-online.target
Wants=network-online.target

[Service]
User=$USER
Environment=YTMP34_KEY=$KEY
Environment=YTMP34_COOKIES=$D/cookies.txt
Environment=YTMP34_MAX=2
Environment=PATH=$D/venv/bin:/usr/local/bin:/usr/bin:/bin
ExecStartPre=-$D/venv/bin/pip install -q -U "yt-dlp[default]" deno
ExecStart=$D/venv/bin/python $D/server.py --host 127.0.0.1 --port 8765
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

# update yt-dlp every night
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
sudo systemctl enable --now ytmp34 ytmp34-update.timer

# open 80/443
REJ=$(sudo iptables -S INPUT | grep -n -- '-j REJECT' | head -1 | cut -d: -f1)
for p in 443 80; do
  sudo iptables -C INPUT -p tcp -m state --state NEW -m tcp --dport $p -j ACCEPT 2>/dev/null ||
    sudo iptables -I INPUT $((REJ - 1)) -p tcp -m state --state NEW -m tcp --dport $p -j ACCEPT
done
sudo sh -c 'iptables-save > /etc/iptables/rules.v4'

printf '%s {\n\treverse_proxy 127.0.0.1:8765\n}\n' "$HOST" | sudo tee /etc/caddy/Caddyfile >/dev/null
sudo systemctl restart caddy

sleep 10
curl -fsS "http://127.0.0.1:8765/ping?key=$KEY" && echo
echo "ytmp34 is at https://$HOST"
