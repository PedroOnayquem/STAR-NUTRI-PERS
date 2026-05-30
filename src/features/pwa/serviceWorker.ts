let refreshing = false

export type ServiceWorkerUpdateEvent = CustomEvent<{
  registration: ServiceWorkerRegistration
}>

export function registerServiceWorker() {
  if (!('serviceWorker' in navigator) || !import.meta.env.PROD) {
    return
  }

  window.addEventListener('load', () => {
    navigator.serviceWorker
      .register('/sw.js')
      .then((registration) => {
        watchForUpdates(registration)
      })
      .catch((error) => {
        if (import.meta.env.DEV) {
          console.warn('Não foi possível registrar o app instalável.', error)
        }
      })
  })

  navigator.serviceWorker.addEventListener('controllerchange', () => {
    if (refreshing) return
    refreshing = true
    window.location.reload()
  })
}

export function applyServiceWorkerUpdate(registration: ServiceWorkerRegistration) {
  const worker = registration.waiting

  if (!worker) {
    return false
  }

  worker.postMessage({ type: 'SKIP_WAITING' })
  return true
}

function watchForUpdates(registration: ServiceWorkerRegistration) {
  registration.addEventListener('updatefound', () => {
    const worker = registration.installing
    if (!worker) return

    worker.addEventListener('statechange', () => {
      if (worker.state === 'installed' && navigator.serviceWorker.controller) {
        window.dispatchEvent(
          new CustomEvent('star-nutri:pwa-update', {
            detail: { registration },
          }) satisfies ServiceWorkerUpdateEvent,
        )
      }
    })
  })
}
