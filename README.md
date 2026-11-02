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

## Useful commands on the Pi

```bash
sudo systemctl status ytmp34      # is it running?
journalctl -u ytmp34 -f           # live log
sudo systemctl restart ytmp34     # restart + update yt-dlp
```
