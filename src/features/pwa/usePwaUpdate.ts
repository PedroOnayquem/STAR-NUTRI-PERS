import { useCallback, useEffect, useState } from 'react'
import {
  applyServiceWorkerUpdate,
  type ServiceWorkerUpdateEvent,
} from './serviceWorker'

export function usePwaUpdate() {
  const [registration, setRegistration] =
    useState<ServiceWorkerRegistration | null>(null)

  useEffect(() => {
    const onUpdate = (event: Event) => {
      setRegistration((event as ServiceWorkerUpdateEvent).detail.registration)
    }

    window.addEventListener('star-nutri:pwa-update', onUpdate)

    return () => {
      window.removeEventListener('star-nutri:pwa-update', onUpdate)
    }
  }, [])

  const updateApp = useCallback(() => {
    if (!registration) return
    applyServiceWorkerUpdate(registration)
  }, [registration])

  return {
    updateApp,
    updateAvailable: Boolean(registration?.waiting),
  }
}
