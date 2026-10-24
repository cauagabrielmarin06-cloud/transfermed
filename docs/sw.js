// Transfermed: funciona sem internet com a última versão vista (rede primeiro, cópia local se cair)
const CACHE = 'tm-202610242118';
const BASE = ['./', 'assets/estilo.css', 'assets/app.js', 'assets/logo.svg', 'assets/brasil.svg', 'assets/inter.woff2', 'assets/municipios.json', 'dados.js'];
self.addEventListener('install', ev => { ev.waitUntil(caches.open(CACHE).then(c => c.addAll(BASE)).then(() => self.skipWaiting())); });
self.addEventListener('activate', ev => { ev.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim())); });
self.addEventListener('fetch', ev => {
  const req = ev.request;
  if (req.method !== 'GET' || new URL(req.url).origin !== location.origin) return;
  ev.respondWith(fetch(req).then(res => { const copia = res.clone(); caches.open(CACHE).then(c => c.put(req, copia)); return res; })
    .catch(() => caches.match(req).then(r => r || caches.match('./'))));
});
