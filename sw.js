const CACHE_NAME = 'cinemaroll-v2';
const assets = [
  './',
  './index.html',
  './search.html',
  './play.html',
  './genre.html',
  './favorites.html',
  './footer.html',
  './script.js',
  './manifest.json',
  'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css'
];

// Install Event
self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(assets);
    })
  );
  self.skipWaiting();
});
