import { useCallback, useEffect, useMemo, useState } from 'react'

type InstallOutcome = 'accepted' | 'dismissed'

type BeforeInstallPromptEvent = Event & {
  prompt: () => Promise<void>
  userChoice: Promise<{
    outcome: InstallOutcome
    platform: string
  }>
}

function isStandaloneMode() {
  return (
    window.matchMedia('(display-mode: standalone)').matches ||
    window.matchMedia('(display-mode: fullscreen)').matches ||
    Boolean((window.navigator as Navigator & { standalone?: boolean }).standalone)
  )
}

function isIosDevice() {
  const ua = window.navigator.userAgent.toLowerCase()
  return /iphone|ipad|ipod/.test(ua)
}

export function usePwaInstallPrompt() {
  const [deferredPrompt, setDeferredPrompt] =
    useState<BeforeInstallPromptEvent | null>(null)
  const [isInstalled, setIsInstalled] = useState(false)
  const [isIos, setIsIos] = useState(false)

  useEffect(() => {
    setIsInstalled(isStandaloneMode())
    setIsIos(isIosDevice())

    const onBeforeInstallPrompt = (event: Event) => {
      event.preventDefault()
      setDeferredPrompt(event as BeforeInstallPromptEvent)
    }

    const onAppInstalled = () => {
      setDeferredPrompt(null)
      setIsInstalled(true)
    }

    const displayModeQuery = window.matchMedia('(display-mode: standalone)')
    const onDisplayModeChange = () => setIsInstalled(isStandaloneMode())

    window.addEventListener('beforeinstallprompt', onBeforeInstallPrompt)
    window.addEventListener('appinstalled', onAppInstalled)
    displayModeQuery.addEventListener('change', onDisplayModeChange)

    return () => {
      window.removeEventListener('beforeinstallprompt', onBeforeInstallPrompt)
      window.removeEventListener('appinstalled', onAppInstalled)
      displayModeQuery.removeEventListener('change', onDisplayModeChange)
    }
  }, [])

  const canInstall = useMemo(
    () => !isInstalled && (Boolean(deferredPrompt) || isIos),
    [deferredPrompt, isInstalled, isIos],
  )

  const installApp = useCallback(async () => {
    if (isInstalled) {
      return { outcome: 'dismissed' as const, needsInstructions: false }
    }

    if (!deferredPrompt) {
      return { outcome: 'dismissed' as const, needsInstructions: isIos }
    }

    await deferredPrompt.prompt()
    const choice = await deferredPrompt.userChoice
    setDeferredPrompt(null)

    if (choice.outcome === 'accepted') {
      setIsInstalled(true)
    }

    return { outcome: choice.outcome, needsInstructions: false }
  }, [deferredPrompt, isInstalled, isIos])

  return {
    canInstall,
    installApp,
    isInstalled,
    isIos,
  }
}
