import type { Session, User } from '@supabase/supabase-js'

export type UserRole = 'admin' | 'nutritionist' | 'patient'

export type AuthProfile = {
  id: string
  fullName: string
  email: string
  role: UserRole
  isActive: boolean
  avatarUrl?: string | null
  phone?: string | null
}

export type AuthState = {
  session: Session | null
  user: User | null
  profile: AuthProfile | null
  loading: boolean
  profileLoading: boolean
  requiresPasswordChange: boolean
  error: string | null
}

export type LoginInput = {
  email: string
  password: string
}

export type ChangePasswordInput = {
  password: string
  confirmPassword: string
}

export type LoginResult = {
  profile: AuthProfile
  requiresPasswordChange: boolean
}

export type RegisterPatientInput = {
  fullName: string
  email: string
  password: string
  confirmPassword: string
}

export type ForgotPasswordInput = {
  email: string
}
