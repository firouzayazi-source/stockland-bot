var CACHE='sl-app-v1784464398';
var SHELL=['./', 'index.html', 'app.css', 'app.js', 'manifest.json',
  'vendor/framework7-bundle.min.js','vendor/framework7-bundle-rtl.min.css',
  'vendor/fonts/Vazirmatn-Regular.woff2','vendor/fonts/Vazirmatn-Medium.woff2',
  'vendor/fonts/Vazirmatn-Bold.woff2','icons/icon-192.png','icons/icon-512.png',
  'icons/icon-180.png','icons/favicon-32.png'];

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
    e.respondWith(fetch(req).then(function(r){var c=r.clone();caches.open(CACHE).then(function(cache){cache.put(req,c)});return r}).catch(function(){return caches.match(req)}));
    return;
  }
  e.respondWith(caches.match(req).then(function(h){
    if(h)return h;
    return fetch(req).then(function(r){if(r&&r.ok){var c=r.clone();caches.open(CACHE).then(function(cache){cache.put(req,c)})}return r});
  }));
});
