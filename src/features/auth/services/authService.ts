import { supabase } from '../../../lib/supabase'
import type { ForgotPasswordInput, LoginInput } from '../types'

function assertSupabase() {
  if (!supabase) {
    throw new Error('Supabase nao configurado. Crie um .env com VITE_SUPABASE_URL e VITE_SUPABASE_ANON_KEY.')
  }

  return supabase
}

export async function signIn(input: LoginInput) {
  const client = assertSupabase()
  const { data, error } = await client.auth.signInWithPassword({
    email: normalizeLoginIdentifier(input.email),
    password: input.password,
  })

  if (error) {
    throw new Error(error.message)
  }

  return data
}

function normalizeLoginIdentifier(identifier: string) {
  const normalized = identifier.trim().toLowerCase()

  if (normalized === 'admin') {
    return 'admin@gmail.com'
  }

  return normalized
}

export async function requestPasswordReset(input: ForgotPasswordInput) {
  const client = assertSupabase()
  const { error } = await client.auth.resetPasswordForEmail(input.email.trim(), {
    redirectTo: `${window.location.origin}/login`,
  })

  if (error) {
    throw new Error(error.message)
  }
}

export async function signOut() {
  const client = assertSupabase()
  const { error } = await client.auth.signOut()

  if (error) {
    throw new Error(error.message)
  }
}

export async function getInitialSession() {
  const client = assertSupabase()
  const { data, error } = await client.auth.getSession()

  if (error) {
    throw new Error(error.message)
  }

  return data.session
}
