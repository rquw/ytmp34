# ytmp34

YouTube to MP3 / MP4. No ads, no redirects. **https://rquw.github.io/ytmp34**

## Features
- No Ads
- No Redirects
- Download from Bookmarks with one click
- Cover Arts and Song Metadata

Converted on Oracle Cloud (Always Free). Its YouTube traffic goes through a Raspberry Pi at home
(`YTMP34_PROXY`, over Tailscale), so YouTube sees a home connection and no cookies are needed.
The Pi also runs its own copy as a slower backup.
Server might go down every now and then. Send an E-Mail to [rquw@icloud.com](mailto:rquw@icloud.com) if you catch it being down!

## Run your own server
On a Raspberry Pi (64-bit Raspberry Pi OS):

```bash
curl -fsSL https://raw.githubusercontent.com/rquw/ytmp34/main/install-pi.sh | bash
```

It prints the server's address at the end. Put it in `index.html` (`const SERVER`).
