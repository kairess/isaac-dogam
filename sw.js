/* 게임을 하다 보면 통신이 끊긴 방에서도 아이템을 확인하고 싶을 때가 있다.
   설치할 때 필요한 파일을 통째로 받아두고, 그 다음부터는 캐시부터 본다. */

// 파일을 고칠 때마다 올린다. 올리지 않으면 이미 방문한 기기가 예전 파일을 계속 쓴다.
const VERSION = "v7";
const CACHE = `isaac-items-${VERSION}`;
const ASSETS = [
  "./",
  "index.html",
  "manifest.webmanifest",
  "assets/style.css",
  "assets/app.js",
  "assets/data/items.json",
  "assets/icons/sprite.webp",
  "assets/icons/app-192.png",
  "assets/icons/app-512.png",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(ASSETS)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET" || new URL(request.url).origin !== location.origin) return;

  event.respondWith(
    caches.match(request).then((hit) => {
      if (hit) {
        // 캐시로 바로 답하고, 뒤에서 조용히 새 걸 받아 다음 방문에 대비한다.
        event.waitUntil(
          fetch(request)
            .then((fresh) => fresh.ok && caches.open(CACHE).then((c) => c.put(request, fresh)))
            .catch(() => {})
        );
        return hit;
      }
      return fetch(request).catch(() => caches.match("index.html"));
    })
  );
});
