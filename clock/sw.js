var cacheName = 'clock-v1';
var filesToCache = [
  './',
  'index.html'
];

// cache files for offline use when installed
self.addEventListener('install', function(e) {
  console.log('[ServiceWorker] Install');
  e.waitUntil(
    caches.open(cacheName).then(function(cache) {
      console.log('[ServiceWorker] Caching files');
      return cache.addAll(filesToCache);
    })
  );
});

// clean up the cache if anything changes
self.addEventListener('activate', function(e) {
  console.log('[ServiceWorker] Activate');
  e.waitUntil(
    caches.keys().then(function(keyList) {
      return Promise.all(keyList.map(function(key) {
        if (key !== cacheName) {
          console.log('[ServiceWorker] Removing old cache', key);
          return caches.delete(key);
        }
      }));
    })
  );
  return self.clients.claim();
});

// try the offline cache first
self.addEventListener('fetch', function(e) {
    e.respondWith(

      caches.match(e.request).then((r) => {
        console.log('[Service Worker] Fetching resource: ' + e.request.url);
        return r || fetch(e.request).then((response) => {
          return caches.open(cacheName).then((cache) => {
            console.log('[Service Worker] Caching new resource: ' + e.request.url);
            cache.put(e.request, response.clone());
            return response;
          });
        });
      })

    );
});
