import type { Session } from '@supabase/supabase-js'
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { supabase } from '../../lib/supabase'
import {
  getInitialSession,
  requestPasswordReset,
  signIn,
  signOut,
} from './services/authService'
import { getCurrentProfile } from './services/profileService'
import type {
  AuthProfile,
  ForgotPasswordInput,
  LoginInput,
} from './types'
import { AuthContext, type AuthContextValue } from './authContextValue'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [profile, setProfile] = useState<AuthProfile | null>(null)
  const [loading, setLoading] = useState(true)
  const [profileLoading, setProfileLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadProfile = useCallback(async (nextSession: Session | null) => {
    if (!nextSession?.user) {
      setProfile(null)
      return null
    }

    setProfileLoading(true)
    try {
      const nextProfile = await getCurrentProfile(nextSession.user.id)
      setProfile(nextProfile)
      return nextProfile
    } finally {
      setProfileLoading(false)
    }
  }, [])

  useEffect(() => {
    let mounted = true

    async function boot() {
      try {
        const nextSession = await getInitialSession()
        if (!mounted) {
          return
        }
        setSession(nextSession)
        await loadProfile(nextSession)
      } catch (caught) {
        setError(caught instanceof Error ? caught.message : 'Erro ao carregar sessao.')
      } finally {
        if (mounted) {
          setLoading(false)
        }
      }
    }

    boot()

    if (!supabase) {
      return () => {
        mounted = false
      }
    }

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, nextSession) => {
      setSession(nextSession)
      loadProfile(nextSession).catch((caught) => {
        setError(caught instanceof Error ? caught.message : 'Erro ao buscar perfil.')
      })
    })

    return () => {
      mounted = false
      subscription.unsubscribe()
    }
  }, [loadProfile])

  const login = useCallback(async (input: LoginInput) => {
    setError(null)
    const { session: nextSession } = await signIn(input)
    setSession(nextSession)
    const nextProfile = await loadProfile(nextSession)

    if (!nextProfile) {
      await signOut()
      setSession(null)
      throw new Error('Usuario sem perfil ativo cadastrado.')
    }

    return nextProfile
  }, [loadProfile])

  const recoverPassword = useCallback(async (input: ForgotPasswordInput) => {
    setError(null)
    await requestPasswordReset(input)
  }, [])

  const logout = useCallback(async () => {
    setError(null)
    await signOut()
    setSession(null)
    setProfile(null)
  }, [])

  const refreshProfile = useCallback(async () => {
    return loadProfile(session)
  }, [loadProfile, session])

  const value = useMemo<AuthContextValue>(
    () => ({
      session,
      user: session?.user ?? null,
      profile,
      loading,
      profileLoading,
      error,
      login,
      recoverPassword,
      logout,
      refreshProfile,
    }),
    [
      error,
      loading,
      login,
      logout,
      profile,
      profileLoading,
      recoverPassword,
      refreshProfile,
      session,
    ],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
