import type {
  ChangePasswordInput,
  LoginInput,
  RegisterPatientInput,
} from './types'

export const STRONG_PASSWORD_RULES = [
  {
    label: 'Pelo menos 8 caracteres',
    test: (password: string) => password.length >= 8,
  },
  {
    label: 'Uma letra maiuscula',
    test: (password: string) => /[A-Z]/.test(password),
  },
  {
    label: 'Uma letra minuscula',
    test: (password: string) => /[a-z]/.test(password),
  },
  {
    label: 'Um numero',
    test: (password: string) => /\d/.test(password),
  },
  {
    label: 'Um caractere especial',
    test: (password: string) => /[^A-Za-z0-9]/.test(password),
  },
] as const

export function validateEmail(email: string) {
  if (!email.trim()) {
    return 'Informe o email.'
  }

  if (email.trim().toLowerCase() === 'admin') {
    return null
  }

  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return 'Informe um email valido.'
  }

  return null
}

export function validatePassword(password: string) {
  if (!password) {
    return 'Informe a senha.'
  }

  if (password.length < 6) {
    return 'A senha deve ter pelo menos 6 caracteres.'
  }

  return null
}

export function validateStrongPassword(password: string) {
  if (!password) {
    return 'Informe a nova senha.'
  }

  if (password.includes(' ')) {
    return 'A senha nao pode conter espacos.'
  }

  const failedRule = STRONG_PASSWORD_RULES.find((rule) => !rule.test(password))
  if (failedRule) {
    return `A senha deve ter ${failedRule.label.toLowerCase()}.`
  }

  return null
}

export function getStrongPasswordChecklist(password: string) {
  return STRONG_PASSWORD_RULES.map((rule) => ({
    label: rule.label,
    passed: rule.test(password),
  }))
}

export function validateLogin(input: LoginInput) {
  const errors: Partial<Record<keyof LoginInput, string>> = {}
  const emailError = validateEmail(input.email)
  const passwordError = validatePassword(input.password)

  if (emailError) {
    errors.email = emailError
  }
  if (passwordError) {
    errors.password = passwordError
  }

  return errors
}

export function validateRegisterPatient(input: RegisterPatientInput) {
  const errors: Partial<Record<keyof RegisterPatientInput, string>> = {}
  const emailError = validateEmail(input.email)
  const passwordError = validatePassword(input.password)

  if (!input.fullName.trim()) {
    errors.fullName = 'Informe o nome completo.'
  }
  if (emailError) {
    errors.email = emailError
  }
  if (passwordError) {
    errors.password = passwordError
  }
  if (input.password !== input.confirmPassword) {
    errors.confirmPassword = 'As senhas nao conferem.'
  }

  return errors
}

export function validateChangePassword(input: ChangePasswordInput) {
  const errors: Partial<Record<keyof ChangePasswordInput, string>> = {}
  const passwordError = validateStrongPassword(input.password)

  if (passwordError) {
    errors.password = passwordError
  }

  if (!input.confirmPassword) {
    errors.confirmPassword = 'Confirme a nova senha.'
  } else if (input.password !== input.confirmPassword) {
    errors.confirmPassword = 'As senhas nao conferem.'
  }

  return errors
}
