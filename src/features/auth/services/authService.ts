import {
  isAuthRetryableFetchError,
  type Session,
  type User,
} from '@supabase/supabase-js'
import { USER_MESSAGES, sanitizeUserMessage } from '../../../constants/messages'
import { apiRequest } from '../../../lib/api'
import { supabase } from '../../../lib/supabase'
import type {
  ChangePasswordInput,
  ForgotPasswordInput,
  LoginInput,
} from '../types'

function assertSupabase() {
  if (!supabase) {
    throw new Error(USER_MESSAGES.unavailableConfig)
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
    if (isAuthRetryableFetchError(error)) {
      throw new Error(USER_MESSAGES.connectionError)
    }
    throw new Error(sanitizeUserMessage(error.message, USER_MESSAGES.loginError))
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
    redirectTo: `${window.location.origin}/auth/reset-password`,
  })

  if (error) {
    throw new Error(sanitizeUserMessage(error.message, 'Não foi possível enviar o e-mail de recuperação.'))
  }
}

export async function signOut() {
  const client = assertSupabase()
  const { error } = await client.auth.signOut()

  if (error) {
    throw new Error(sanitizeUserMessage(error.message, USER_MESSAGES.actionError))
  }
}

export async function getInitialSession() {
  const client = assertSupabase()
  const { data, error } = await client.auth.getSession()

  if (error) {
    throw new Error(sanitizeUserMessage(error.message, USER_MESSAGES.missingSession))
  }

  return data.session
}

export function needsPasswordChange(user: User | null | undefined) {
  const appFlag = user?.app_metadata?.must_change_password
  if (appFlag !== undefined) {
    return appFlag === true || appFlag === 'true'
  }

  const flag = user?.user_metadata?.must_change_password
  return flag === true || flag === 'true'
}

export async function updatePassword(
  input: ChangePasswordInput,
  session: Session | null,
) {
  const client = assertSupabase()
  await apiRequest('/api/auth/change-password', session, {
    body: JSON.stringify({ password: input.password }),
    method: 'POST',
  })

  const { data, error } = await client.auth.refreshSession()

  if (error || !data.user) {
    throw new Error(
      sanitizeUserMessage(
        error?.message,
        'Senha atualizada. Entre novamente para continuar.',
      ),
    )
  }

  return data.user
}

export async function updateRecoveredPassword(input: ChangePasswordInput) {
  const client = assertSupabase()
  const { data, error } = await client.auth.updateUser({
    password: input.password,
  })

  if (error || !data.user) {
    throw new Error(
      sanitizeUserMessage(
        error?.message,
        'Não foi possível atualizar a senha. Solicite um novo link de recuperação.',
      ),
    )
  }

  return data.user
}
