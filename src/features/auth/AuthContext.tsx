import type { Session } from '@supabase/supabase-js'
import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from 'react'
import { supabase } from '../../lib/supabase'
import {
  getInitialSession,
  needsPasswordChange,
  requestPasswordReset,
  signIn,
  signOut,
  updatePassword,
} from './services/authService'
import { getCurrentProfile } from './services/profileService'
import type {
  AuthProfile,
  ChangePasswordInput,
  ForgotPasswordInput,
  LoginInput,
  LoginResult,
} from './types'
import { AuthContext, type AuthContextValue } from './authContextValue'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [profile, setProfile] = useState<AuthProfile | null>(null)
  const [loading, setLoading] = useState(true)
  const [profileLoading, setProfileLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const profileCacheRef = useRef(new Map<string, AuthProfile | null>())
  const profileRequestRef = useRef<{
    promise: Promise<AuthProfile | null>
    userId: string
  } | null>(null)
  const requiresPasswordChange = needsPasswordChange(session?.user)

  const loadProfile = useCallback(async (
    nextSession: Session | null,
    options?: { force?: boolean },
  ) => {
    if (!nextSession?.user) {
      setProfile(null)
      return null
    }

    const userId = nextSession.user.id
    if (!options?.force && profileCacheRef.current.has(userId)) {
      const cached = profileCacheRef.current.get(userId) ?? null
      setProfile(cached)
      return cached
    }

    const currentRequest = profileRequestRef.current
    if (!options?.force && currentRequest?.userId === userId) {
      const cached = await currentRequest.promise
      setProfile(cached)
      return cached
    }

    setProfileLoading(true)
    const request = getCurrentProfile(userId).then((nextProfile) => {
      profileCacheRef.current.set(userId, nextProfile)
      return nextProfile
    })
    profileRequestRef.current = { promise: request, userId }
    try {
      const nextProfile = await request
      setProfile(nextProfile)
      return nextProfile
    } finally {
      if (profileRequestRef.current?.promise === request) {
        profileRequestRef.current = null
      }
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

  const login = useCallback(async (input: LoginInput): Promise<LoginResult> => {
    setError(null)
    const { session: nextSession } = await signIn(input)
    setSession(nextSession)
    const nextProfile = await loadProfile(nextSession)

    if (!nextProfile) {
      await signOut()
      setSession(null)
      throw new Error('Usuario sem perfil ativo cadastrado.')
    }

    return {
      profile: nextProfile,
      requiresPasswordChange: needsPasswordChange(nextSession?.user),
    }
  }, [loadProfile])

  const changePassword = useCallback(async (input: ChangePasswordInput) => {
    setError(null)
    await updatePassword(input)
    const nextSession = await getInitialSession()
    setSession(nextSession)
    return await loadProfile(nextSession)
  }, [loadProfile])

  const recoverPassword = useCallback(async (input: ForgotPasswordInput) => {
    setError(null)
    await requestPasswordReset(input)
  }, [])

  const logout = useCallback(async () => {
    setError(null)
    await signOut()
    profileCacheRef.current.clear()
    setSession(null)
    setProfile(null)
  }, [])

  const refreshProfile = useCallback(async () => {
    return loadProfile(session, { force: true })
  }, [loadProfile, session])

  const value = useMemo<AuthContextValue>(
    () => ({
      session,
      user: session?.user ?? null,
      profile,
      loading,
      profileLoading,
      requiresPasswordChange,
      error,
      changePassword,
      login,
      recoverPassword,
      logout,
      refreshProfile,
    }),
    [
      changePassword,
      error,
      loading,
      login,
      logout,
      profile,
      profileLoading,
      recoverPassword,
      refreshProfile,
      requiresPasswordChange,
      session,
    ],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
