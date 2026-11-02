// ytmp34 service worker: makes the site installable and lets the page open without a connection.
// Only this site's own files are handled (network first, cache as fallback); downloads from the
// server are a different origin and pass straight through.
const CACHE = "ytmp34-v2";
const SHELL = ["./", "manifest.webmanifest", "icon.svg", "icon-192.png", "icon-512.png", "apple-touch-icon.png"];

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", e => {
  e.waitUntil(caches.keys()
    .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", e => {
  const url = new URL(e.request.url);
  if (e.request.method !== "GET" || url.origin !== location.origin) return;
  // "no-cache" revalidates with GitHub Pages instead of reusing its 10-minute browser cache, so updates show at once.
  e.respondWith(fetch(e.request, { cache: "no-cache" })
    .then(r => { if (r.ok) { const copy = r.clone(); caches.open(CACHE).then(c => c.put(e.request, copy)); } return r; })
    .catch(() => caches.match(e.request, { ignoreSearch: true })));
});
