import { createContext } from 'react'
import type {
  AuthProfile,
  AuthState,
  ChangePasswordInput,
  ForgotPasswordInput,
  LoginInput,
  LoginResult,
} from './types'

export type AuthContextValue = AuthState & {
  changePassword: (input: ChangePasswordInput) => Promise<AuthProfile | null>
  resetRecoveredPassword: (input: ChangePasswordInput) => Promise<void>
  login: (input: LoginInput) => Promise<LoginResult>
  recoverPassword: (input: ForgotPasswordInput) => Promise<void>
  logout: () => Promise<void>
  refreshProfile: () => Promise<AuthProfile | null>
}

export const AuthContext = createContext<AuthContextValue | null>(null)
