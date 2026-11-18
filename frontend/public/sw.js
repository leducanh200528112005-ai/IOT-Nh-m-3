const SHELL_CACHE = 'flood-shell-v1';
const TILE_CACHE = 'flood-tiles-v1';

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE).then((cache) => cache.addAll(['/', '/index.html', '/icon.svg', '/manifest.webmanifest'])).catch(() => undefined)
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);

  // Never intercept live API or streaming calls cleanly.
  if (url.pathname.startsWith('/api/')) return;

  // Cache OSM map tiles stale-while-revalidate for offline readability.
  if (url.hostname.includes('tile.openstreetmap.org')) {
    event.respondWith(
      caches.open(TILE_CACHE).then(async (cache) => {
        const cached = await cache.match(req);
        const networkPromise = fetch(req)
          .then((resp) => {
            if (resp && resp.ok) cache.put(req, resp.clone());
            return resp;
          })
          .catch(() => cached);
        return cached || networkPromise;
      })
    );
    return;
  }

  // App shell static assets: network-first fallback to cache.
  if (url.origin === self.location.origin) {
    event.respondWith(
      fetch(req)
        .then((resp) => {
          if (resp && resp.ok) {
            const copy = resp.clone();
            caches.open(SHELL_CACHE).then((c) => c.put(req, copy));
          }
          return resp;
        })
        .catch(() => caches.match(req).then((m) => m || caches.match('/index.html')))
    );
  }
});
