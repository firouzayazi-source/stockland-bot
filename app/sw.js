var CACHE='sl-app-v23';
var SHELL=['./', 'index.html', 'app.css', 'app.js', 'manifest.json',
  'vendor/framework7-bundle.min.js','vendor/framework7-bundle-rtl.min.css',
  'vendor/fonts/Vazirmatn-Regular.woff2','vendor/fonts/Vazirmatn-Medium.woff2',
  'vendor/fonts/Vazirmatn-Bold.woff2','icons/icon-192.png','icons/icon-512.png',
  'icons/icon-180.png','icons/favicon-32.png','icons/logo-sl.png'];
// سقف تعداد ورودی کش — بدون این، هر عکس محصول/پاسخ API که یه‌بار فچ بشه برای
// همیشه روی دستگاه کاربر می‌مونه (بدون هیچ eviction ای)، یعنی کش با گذر زمان
// بی‌پایان رشد می‌کنه. بعد از هر put، اگه از سقف رد شد، قدیمی‌ترین ورودی‌ها
// (به ترتیب همون‌طور که Cache API برمی‌گردونه — تقریباً insertion-order) حذف می‌شن.
var MAX_CACHE_ENTRIES=150;
function trimCache(cacheName,maxEntries){
  caches.open(cacheName).then(function(cache){
    cache.keys().then(function(keys){
      if(keys.length<=maxEntries)return;
      var toDelete=keys.slice(0,keys.length-maxEntries);
      toDelete.forEach(function(k){cache.delete(k)});
    });
  });
}

self.addEventListener('install',function(e){
  e.waitUntil(caches.open(CACHE).then(function(c){
    return Promise.allSettled(SHELL.map(function(u){return c.add(u)}));
  }).then(function(){return self.skipWaiting()}));
});
self.addEventListener('activate',function(e){
  e.waitUntil(caches.keys().then(function(keys){
    return Promise.all(keys.filter(function(k){return k!==CACHE}).map(function(k){return caches.delete(k)}));
  }).then(function(){return self.clients.claim()}));
});
self.addEventListener('fetch',function(e){
  var req=e.request;if(req.method!=='GET')return;
  var url=new URL(req.url);if(url.origin!==location.origin)return;
  if(url.pathname.indexOf('/api/')===0){
    e.respondWith(fetch(req).then(function(r){var c=r.clone();caches.open(CACHE).then(function(cache){cache.put(req,c);trimCache(CACHE,MAX_CACHE_ENTRIES)});return r}).catch(function(){return caches.match(req)}));
    return;
  }
  e.respondWith(caches.match(req).then(function(h){
    if(h)return h;
    return fetch(req).then(function(r){if(r&&r.ok){var c=r.clone();caches.open(CACHE).then(function(cache){cache.put(req,c);trimCache(CACHE,MAX_CACHE_ENTRIES)})}return r});
  }));
});
