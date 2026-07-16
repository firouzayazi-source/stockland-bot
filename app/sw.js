/* استوک‌لند PWA — Service Worker */
var CACHE = 'sl-app-v1';
var SHELL = [
  './', 'index.html', 'app.css', 'app.js', 'manifest.json',
  'vendor/framework7-bundle.min.js',
  'vendor/framework7-bundle-rtl.min.css',
  'vendor/fonts/Vazirmatn-Regular.woff2',
  'vendor/fonts/Vazirmatn-Medium.woff2',
  'vendor/fonts/Vazirmatn-Bold.woff2',
  'icons/icon-192.png', 'icons/icon-512.png'
];

self.addEventListener('install', function (e) {
  e.waitUntil(
    caches.open(CACHE).then(function (c) {
      // تک‌به‌تک؛ اگر فایلی هنوز نبود (مثلاً vendor)، نصب SW خراب نشود
      return Promise.allSettled(SHELL.map(function (u) { return c.add(u); }));
    }).then(function () { return self.skipWaiting(); })
  );
});

self.addEventListener('activate', function (e) {
  e.waitUntil(
    caches.keys().then(function (keys) {
      return Promise.all(keys.filter(function (k) { return k !== CACHE; })
        .map(function (k) { return caches.delete(k); }));
    }).then(function () { return self.clients.claim(); })
  );
});

self.addEventListener('fetch', function (e) {
  var req = e.request;
  if (req.method !== 'GET') return;
  var url = new URL(req.url);
  if (url.origin !== location.origin) return;

  // API: اول شبکه، بعد کش (تا محتوا همیشه تازه باشد ولی آفلاین هم چیزی نشان دهد)
  if (url.pathname.indexOf('/api/') === 0) {
    e.respondWith(
      fetch(req).then(function (res) {
        var copy = res.clone();
        caches.open(CACHE).then(function (c) { c.put(req, copy); });
        return res;
      }).catch(function () { return caches.match(req); })
    );
    return;
  }

  // پوسته و مدیا: اول کش، بعد شبکه
  e.respondWith(
    caches.match(req).then(function (hit) {
      if (hit) return hit;
      return fetch(req).then(function (res) {
        if (res && res.ok) {
          var copy = res.clone();
          caches.open(CACHE).then(function (c) { c.put(req, copy); });
        }
        return res;
      });
    })
  );
});
