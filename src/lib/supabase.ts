import { createClient } from '@supabase/supabase-js'
import { getAppConfig } from './runtimeConfig'

const supabaseUrl = getAppConfig('VITE_SUPABASE_URL')
const supabaseAnonKey = getAppConfig('VITE_SUPABASE_ANON_KEY')

export const isSupabaseConfigured = Boolean(supabaseUrl && supabaseAnonKey)

export const supabase = isSupabaseConfigured
  ? createClient(supabaseUrl!, supabaseAnonKey!)
  : null
