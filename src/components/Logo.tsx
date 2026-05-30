import { useEffect, useState } from 'react'

type LogoProps = {
  className?: string
  showText?: boolean
}

function getPreferredLogo() {
  if (typeof document === 'undefined') {
    return '/CLARO.svg'
  }

  const storedTheme =
    localStorage.getItem('star-nutri-theme') ?? localStorage.getItem('theme')
  const isDark =
    document.documentElement.classList.contains('dark') || storedTheme === 'dark'

  return isDark ? '/ESCURO.svg' : '/CLARO.svg'
}

export function Logo({
  className = 'h-12 w-auto max-w-[180px]',
  showText = true,
}: LogoProps) {
  const [logoSrc, setLogoSrc] = useState(getPreferredLogo)
  const [hasError, setHasError] = useState(false)

  useEffect(() => {
    const updateLogo = () => {
      setLogoSrc(getPreferredLogo())
      setHasError(false)
    }
    const observer = new MutationObserver(updateLogo)

    observer.observe(document.documentElement, {
      attributeFilter: ['class'],
      attributes: true,
    })

    window.addEventListener('storage', updateLogo)

    return () => {
      observer.disconnect()
      window.removeEventListener('storage', updateLogo)
    }
  }, [])

  return (
    <div className="flex min-w-0 items-center gap-3">
      {hasError ? (
        <span className="text-base font-black leading-none">Star Nutri</span>
      ) : (
        <img
          alt="Star Nutri"
          className={`${className} block shrink-0 object-contain`}
          decoding="async"
          onError={() => {
            console.error('Erro ao carregar logo:', logoSrc)
            setHasError(true)
          }}
          src={logoSrc}
        />
      )}

      {showText && (
        <div className="min-w-0 leading-tight">
          <p className="truncate font-semibold text-slate-950 dark:text-white">
            Star Nutri
          </p>
          <p className="truncate text-xs text-slate-500 dark:text-slate-400">
            Nutrição inteligente
          </p>
        </div>
      )}
    </div>
  )
}
