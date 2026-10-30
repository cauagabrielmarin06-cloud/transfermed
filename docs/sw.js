// Transfermed: funciona sem internet com a última versão vista.
// HTML sempre da rede (sem a cópia do navegador); o resto da rede primeiro; cópia local só se a rede cair.
// O service worker novo assume na hora e apaga os caches antigos.
const CACHE = 'tm-202610301715';
const BASE = ['./', 'assets/estilo.css', 'assets/app.js', 'assets/logo.svg', 'assets/brasil.svg', 'assets/inter.woff2', 'assets/municipios.json', 'dados.js'];
self.addEventListener('install', ev => {
  self.skipWaiting();  // não espera as abas antigas fecharem, nem depende de a cópia da base dar certo
  ev.waitUntil(caches.open(CACHE).then(c => Promise.all(BASE.map(u => c.add(new Request(u, {cache: 'reload'})).catch(() => {})))));
});
self.addEventListener('activate', ev => {
  ev.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', ev => {
  const req = ev.request;
  if (req.method !== 'GET' || new URL(req.url).origin !== location.origin) return;
  const html = req.mode === 'navigate' || (req.headers.get('accept') || '').includes('text/html');
  ev.respondWith(fetch(req, html ? {cache: 'no-cache'} : {}).then(res => {
    if (res.ok) { const copia = res.clone(); caches.open(CACHE).then(c => c.put(req, copia)); }
    return res;
  }).catch(() => caches.match(req, {ignoreSearch: true}).then(r => r || (html ? caches.match('./') : Response.error()))));
});
