# ytmp34

YouTube → MP3 / MP4. No ads, no redirects. **https://rquw.github.io/ytmp34**

The page is static (GitHub Pages). The actual downloading is done by yt-dlp on your own
Raspberry Pi, reachable from anywhere through a free Tailscale Funnel HTTPS address.

## Pi setup (once)

1. Create a free account at [tailscale.com](https://tailscale.com) (Google login works).
2. On the Pi, run:

   ```bash
   curl -fsSL https://raw.githubusercontent.com/rquw/ytmp34/main/install-pi.sh | bash
   ```

   It installs ffmpeg + yt-dlp, a systemd service that starts on boot, a nightly yt-dlp update,
   and Tailscale. When it prints a login link, open it and sign in. If it says Funnel isn't
   enabled, open the link it shows, click enable, and run the command again.
3. It ends by printing a setup link like
   `https://rquw.github.io/ytmp34/#s=https://pi.tailXXXX.ts.net&k=...`.
   Open that once on your phone (and any PC). Settings are saved; bookmark the plain site.

The key keeps strangers from using your Pi. It's stored in `~/ytmp34/key`.

## Current host: Oracle Cloud (Always Free)

Runs on an Always Free `VM.Standard.E2.1.Micro` (Ubuntu 24.04, Frankfurt) at
`https://92-5-64-38.sslip.io`: Caddy (free Let's Encrypt cert via sslip.io) → `server.py` on
127.0.0.1:8765. The key is in `~/ytmp34/key` on the VM.

YouTube blocks cloud IPs as bots, so the server uses cookies from a **spare** Google account in
`~/ytmp34/cookies.txt`. When downloads start failing with "Sign in to confirm you're not a bot",
export fresh cookies (Incognito window, "Get cookies.txt LOCALLY", close the window right after) and:

```bash
scp -i ~/Downloads/ssh-key-2026-10-22.key ~/Downloads/youtube-cookies.txt ubuntu@92.5.64.38:ytmp34/cookies.txt
```

## Useful commands on the server

```bash
sudo systemctl status ytmp34      # is it running?
journalctl -u ytmp34 -f           # live log
sudo systemctl restart ytmp34     # restart + update yt-dlp
```
