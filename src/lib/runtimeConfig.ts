type RuntimeConfigKey =
  | 'VITE_API_BASE_URL'
  | 'VITE_SUPABASE_ANON_KEY'
  | 'VITE_SUPABASE_URL'

type RuntimeConfig = Partial<Record<RuntimeConfigKey, string>>

function readRuntimeConfig(): RuntimeConfig {
  if (typeof window === 'undefined') {
    return {}
  }

  return window.__APP_CONFIG__ ?? {}
}

export function getAppConfig(key: RuntimeConfigKey): string | undefined {
  const runtimeValue = readRuntimeConfig()[key]

  if (typeof runtimeValue === 'string' && runtimeValue.trim()) {
    return runtimeValue.trim()
  }

  const buildValue = import.meta.env[key] as string | undefined

  if (typeof buildValue === 'string' && buildValue.trim()) {
    return buildValue.trim()
  }

  return undefined
}
