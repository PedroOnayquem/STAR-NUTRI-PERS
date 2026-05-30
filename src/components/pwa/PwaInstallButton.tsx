import { useState } from 'react'
import { Download, RefreshCw, Share2, X } from 'lucide-react'
import { Button } from '../ui/Button'
import { usePwaInstallPrompt } from '../../features/pwa/usePwaInstallPrompt'
import { usePwaUpdate } from '../../features/pwa/usePwaUpdate'

export function PwaInstallButton() {
  const { canInstall, installApp, isInstalled, isIos } = usePwaInstallPrompt()
  const { updateApp, updateAvailable } = usePwaUpdate()
  const [showIosInstructions, setShowIosInstructions] = useState(false)

  if (!canInstall && !updateAvailable) {
    return null
  }

  if (updateAvailable) {
    return (
      <Button
        onClick={updateApp}
        size="sm"
        title="Atualizar aplicativo"
        type="button"
        variant="premium"
      >
        <RefreshCw size={17} />
        <span className="hidden sm:inline">Atualizar agora</span>
      </Button>
    )
  }

  if (isInstalled) {
    return null
  }

  async function handleInstall() {
    const result = await installApp()
    if (result.needsInstructions) {
      setShowIosInstructions(true)
    }
  }

  return (
    <>
      <Button
        onClick={handleInstall}
        size="sm"
        title={isIos ? 'Instalar Star Nutri no iPhone ou iPad' : 'Instalar app'}
        type="button"
        variant="secondary"
      >
        <Download size={17} />
        <span className="hidden sm:inline">Instalar app</span>
        <span className="sm:hidden">Instalar</span>
      </Button>

      {showIosInstructions && (
        <div
          aria-modal="true"
          className="fixed inset-0 z-50 flex items-end justify-center bg-slate-950/70 px-4 pb-4 backdrop-blur-sm sm:items-center sm:pb-0"
          role="dialog"
        >
          <div className="w-full max-w-sm rounded-3xl border border-white/10 bg-slate-950 p-5 text-white shadow-[0_24px_80px_rgba(2,6,23,0.45)]">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="inline-flex rounded-2xl bg-emerald-400/15 p-3 text-emerald-300">
                  <Share2 size={22} />
                </div>
                <h2 className="mt-4 text-lg font-black">
                  Instalar Star Nutri
                </h2>
                <p className="mt-2 text-sm leading-6 text-slate-300">
                  No iPhone ou iPad, a instalação é feita pelo menu de compartilhamento do Safari.
                </p>
              </div>
              <Button
                aria-label="Fechar instruções"
                onClick={() => setShowIosInstructions(false)}
                size="icon"
                type="button"
                variant="ghost"
              >
                <X size={18} />
              </Button>
            </div>

            <ol className="mt-5 space-y-3 text-sm text-slate-200">
              <li className="rounded-2xl border border-white/10 bg-white/[0.04] p-3">
                1. Toque no botão de compartilhar do Safari.
              </li>
              <li className="rounded-2xl border border-white/10 bg-white/[0.04] p-3">
                2. Selecione “Adicionar à Tela de Início”.
              </li>
              <li className="rounded-2xl border border-white/10 bg-white/[0.04] p-3">
                3. Confirme em “Adicionar”.
              </li>
            </ol>

            <Button
              className="mt-5 w-full"
              onClick={() => setShowIosInstructions(false)}
              type="button"
              variant="premium"
            >
              Entendi
            </Button>
          </div>
        </div>
      )}
    </>
  )
}
