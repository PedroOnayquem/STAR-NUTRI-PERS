import type { LoginInput, RegisterPatientInput } from './types'

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
