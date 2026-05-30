const CACHE_NAME = 'star-nutri-static-v3'
const APP_SHELL = [
  '/',
  '/manifest.webmanifest',
  '/CLARO.svg',
  '/ESCURO.svg',
]

const SENSITIVE_PATHS = [
  '/api/',
  '/backend/',
  '/auth/',
  '/rest/',
  '/storage/',
]

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(CACHE_NAME)
      .then((cache) =>
        Promise.all(
          APP_SHELL.map((path) => cache.add(path).catch(() => undefined)),
        ),
      )
      .catch(() => undefined),
  )
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => key !== CACHE_NAME)
            .map((key) => caches.delete(key)),
        ),
      )
      .then(() => self.clients.claim()),
  )
})

self.addEventListener('message', (event) => {
  if (event.data?.type === 'SKIP_WAITING') {
    self.skipWaiting()
  }
})

self.addEventListener('fetch', (event) => {
  const { request } = event

  if (request.method !== 'GET') return

  const url = new URL(request.url)

  if (url.origin !== self.location.origin) return
  if (SENSITIVE_PATHS.some((path) => url.pathname.startsWith(path))) return
  if (url.pathname === '/config.js') return

  if (request.mode === 'navigate') {
    event.respondWith(networkFirst(request))
    return
  }

  if (
    url.pathname.startsWith('/assets/') ||
    url.pathname === '/CLARO.svg' ||
    url.pathname === '/ESCURO.svg' ||
    url.pathname === '/manifest.webmanifest'
  ) {
    event.respondWith(staleWhileRevalidate(request))
  }
})

async function networkFirst(request) {
  const cache = await caches.open(CACHE_NAME)

  try {
    const response = await fetch(request)
    if (response.ok) {
      cache.put(request, response.clone())
      cache.put('/', response.clone())
    }
    return response
  } catch {
    return (await cache.match(request)) ?? (await cache.match('/'))
  }
}

async function staleWhileRevalidate(request) {
  const cache = await caches.open(CACHE_NAME)
  const cached = await cache.match(request)
  const fetched = fetch(request)
    .then((response) => {
      if (response.ok) {
        cache.put(request, response.clone())
      }
      return response
    })
    .catch(() => cached)

  return cached ?? fetched
}
