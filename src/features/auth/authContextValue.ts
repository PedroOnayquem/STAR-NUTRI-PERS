import { createContext } from 'react'
import type { AuthProfile, AuthState, ForgotPasswordInput, LoginInput } from './types'

export type AuthContextValue = AuthState & {
  login: (input: LoginInput) => Promise<AuthProfile>
  recoverPassword: (input: ForgotPasswordInput) => Promise<void>
  logout: () => Promise<void>
  refreshProfile: () => Promise<AuthProfile | null>
}

export const AuthContext = createContext<AuthContextValue | null>(null)
