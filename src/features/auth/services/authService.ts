import type { User } from '@supabase/supabase-js'
import { USER_MESSAGES, sanitizeUserMessage } from '../../../constants/messages'
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
    redirectTo: `${window.location.origin}/login`,
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
  const flag = user?.user_metadata?.must_change_password
  return flag === true || flag === 'true'
}

export async function updatePassword(input: ChangePasswordInput) {
  const client = assertSupabase()
  const currentUserResponse = await client.auth.getUser()

  if (currentUserResponse.error) {
    throw new Error(sanitizeUserMessage(currentUserResponse.error.message, USER_MESSAGES.missingSession))
  }

  const currentMetadata = currentUserResponse.data.user?.user_metadata ?? {}
  const { data, error } = await client.auth.updateUser({
    password: input.password,
    data: {
      ...currentMetadata,
      must_change_password: false,
      password_changed_at: new Date().toISOString(),
    },
  })

  if (error) {
    throw new Error(sanitizeUserMessage(error.message, 'Não foi possível atualizar a senha.'))
  }

  return data.user
}
