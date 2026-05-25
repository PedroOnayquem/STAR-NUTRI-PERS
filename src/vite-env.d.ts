/// <reference types="vite/client" />

interface Window {
  __APP_CONFIG__?: Partial<
    Record<
      'VITE_API_BASE_URL' | 'VITE_SUPABASE_ANON_KEY' | 'VITE_SUPABASE_URL',
      string
    >
  >
}
