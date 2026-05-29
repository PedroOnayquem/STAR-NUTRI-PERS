export const USER_MESSAGES = {
  actionError: 'Não foi possível concluir esta ação. Tente novamente em instantes.',
  connectionError: 'Não foi possível conectar ao Star Nutri. Tente novamente em instantes.',
  loginError: 'E-mail ou senha incorretos. Verifique os dados e tente novamente.',
  missingSession: 'Sua sessão expirou. Entre novamente para continuar.',
  unavailableConfig: 'O Star Nutri não está disponível no momento. Tente novamente em instantes.',
} as const

const technicalPatterns = [
  /supabase/i,
  /\bbackend\b/i,
  /\bauth\b/i,
  /\bschema\b/i,
  /\bworkspace\b/i,
  /\bquery\b/i,
  /\bmutation\b/i,
  /\bpayload\b/i,
  /\bdebug\b/i,
  /\bmock\b/i,
  /openai/i,
  /\bOCR\b/i,
  /\bPGRST\d+\b/i,
  /VITE_/i,
  /failed to fetch/i,
  /dynamically imported module/i,
]

export function friendlyErrorMessage(
  error: unknown,
  fallback: string = USER_MESSAGES.actionError,
) {
  if (!(error instanceof Error) || !error.message.trim()) {
    return fallback
  }

  return sanitizeUserMessage(error.message, fallback)
}

export function sanitizeUserMessage(
  message: string | null | undefined,
  fallback: string = USER_MESSAGES.actionError,
) {
  const text = message?.trim()
  if (!text) return fallback

  if (/invalid login credentials/i.test(text)) {
    return USER_MESSAGES.loginError
  }

  if (/email not confirmed/i.test(text)) {
    return 'Confirme seu e-mail antes de entrar.'
  }

  if (/session|jwt/i.test(text) && /expired|invalid|missing|not found/i.test(text)) {
    return USER_MESSAGES.missingSession
  }

  if (technicalPatterns.some((pattern) => pattern.test(text))) {
    return fallback
  }

  return text
}
