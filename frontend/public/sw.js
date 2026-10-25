// HomeMind Hub Service Worker for PWA & Fast Asset Caching
const CACHE_NAME = "homemind-hub-v4";
const OFFLINE_URL = "/";

const PRECACHE_ASSETS = [
  "/",
  "/manifest.json",
  "/favicon.svg",
  "/icon-192.svg",
  "/icon-512.svg"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(PRECACHE_ASSETS);
    })
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cache) => {
          if (cache !== CACHE_NAME) {
            return caches.delete(cache);
          }
        })
      );
    })
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  // Do not intercept API, healthcheck, WebSocket, or Simulator proxy routes
  if (
    url.pathname.startsWith("/api/") ||
    url.pathname.startsWith("/health") ||
    url.pathname.startsWith("/mqtt") ||
    url.pathname.startsWith("/simulator") ||
    event.request.method !== "GET"
  ) {
    return;
  }

  // Network first with cache fallback for HTML pages
  if (event.request.mode === "navigate") {
    event.respondWith(
      fetch(event.request).catch(() => {
        return caches.match(OFFLINE_URL);
      })
    );
    return;
  }

  // Cache first for static hashed assets (.js, .css, .svg, fonts)
  if (
    url.pathname.startsWith("/assets/") ||
    url.pathname.endsWith(".svg") ||
    url.pathname.endsWith(".woff2")
  ) {
    event.respondWith(
      caches.match(event.request).then((cached) => {
        if (cached) return cached;
        return fetch(event.request).then((response) => {
          if (response && response.status === 200) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then((cache) => {
              cache.put(event.request, clone);
            });
          }
          return response;
        });
      })
    );
    return;
  }
});
