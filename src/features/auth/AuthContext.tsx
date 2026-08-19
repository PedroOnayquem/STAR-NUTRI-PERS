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
import { USER_MESSAGES, friendlyErrorMessage } from '../../constants/messages'
import {
  getInitialSession,
  needsPasswordChange,
  requestPasswordReset,
  signIn,
  signOut,
  updatePassword,
  updateRecoveredPassword,
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

const PASSWORD_RECOVERY_STORAGE_KEY = 'star-nutri-password-recovery'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [profile, setProfile] = useState<AuthProfile | null>(null)
  const [loading, setLoading] = useState(true)
  const [profileLoading, setProfileLoading] = useState(false)
  const [isPasswordRecovery, setIsPasswordRecovery] = useState(
    () => sessionStorage.getItem(PASSWORD_RECOVERY_STORAGE_KEY) === 'true',
  )
  const [error, setError] = useState<string | null>(null)
  const passwordRecoveryRef = useRef(isPasswordRecovery)
  const profileCacheRef = useRef(new Map<string, AuthProfile | null>())
  const profileRequestRef = useRef<{
    promise: Promise<AuthProfile | null>
    userId: string
  } | null>(null)
  const requiresPasswordChange = needsPasswordChange(session?.user)

  const setPasswordRecoveryMode = useCallback((active: boolean) => {
    passwordRecoveryRef.current = active
    setIsPasswordRecovery(active)
    if (active) {
      sessionStorage.setItem(PASSWORD_RECOVERY_STORAGE_KEY, 'true')
    } else {
      sessionStorage.removeItem(PASSWORD_RECOVERY_STORAGE_KEY)
    }
  }, [])

  const shouldDeferProfile = useCallback((nextSession: Session | null) => {
    return (
      needsPasswordChange(nextSession?.user) ||
      passwordRecoveryRef.current
    )
  }, [])

  const loadProfile = useCallback(async (
    nextSession: Session | null,
    options?: { force?: boolean },
  ) => {
    if (!nextSession?.user) {
      setProfile(null)
      return null
    }

    if (shouldDeferProfile(nextSession)) {
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
      if (shouldDeferProfile(nextSession)) {
        setProfile(null)
        return null
      }
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
      if (shouldDeferProfile(nextSession)) {
        setProfile(null)
        return null
      }
      setProfile(nextProfile)
      return nextProfile
    } finally {
      if (profileRequestRef.current?.promise === request) {
        profileRequestRef.current = null
      }
      setProfileLoading(false)
    }
  }, [shouldDeferProfile])

  useEffect(() => {
    let mounted = true

    async function boot() {
      try {
        const nextSession = await getInitialSession()
        if (!mounted) {
          return
        }
        setSession(nextSession)
        if (shouldDeferProfile(nextSession)) {
          setProfile(null)
        } else {
          await loadProfile(nextSession)
        }
      } catch (caught) {
        setError(friendlyErrorMessage(caught, USER_MESSAGES.missingSession))
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
    } = supabase.auth.onAuthStateChange((event, nextSession) => {
      setSession(nextSession)

      if (event === 'PASSWORD_RECOVERY') {
        setPasswordRecoveryMode(true)
        setProfile(null)
        return
      }

      if (event === 'SIGNED_OUT') {
        setPasswordRecoveryMode(false)
        profileCacheRef.current.clear()
      }

      if (shouldDeferProfile(nextSession)) {
        setProfile(null)
        return
      }

      loadProfile(nextSession).catch((caught) => {
        setError(friendlyErrorMessage(caught, USER_MESSAGES.actionError))
      })
    })

    return () => {
      mounted = false
      subscription.unsubscribe()
    }
  }, [loadProfile, setPasswordRecoveryMode, shouldDeferProfile])

  const login = useCallback(async (input: LoginInput): Promise<LoginResult> => {
    setError(null)
    const { session: nextSession } = await signIn(input)
    setPasswordRecoveryMode(false)
    setSession(nextSession)

    const passwordChangeRequired = needsPasswordChange(nextSession?.user)
    if (passwordChangeRequired) {
      setProfile(null)
      return {
        profile: null,
        requiresPasswordChange: true,
      }
    }

    try {
      const nextProfile = await loadProfile(nextSession)

      if (!nextProfile) {
        throw new Error('Seu perfil ainda não está ativo. Fale com o responsável pela sua conta.')
      }

      return {
        profile: nextProfile,
        requiresPasswordChange: false,
      }
    } catch (caught) {
      await signOut().catch(() => undefined)
      if (nextSession?.user.id) {
        profileCacheRef.current.delete(nextSession.user.id)
      }
      setSession(null)
      setProfile(null)
      throw caught
    }
  }, [loadProfile, setPasswordRecoveryMode])

  const changePassword = useCallback(async (input: ChangePasswordInput) => {
    setError(null)
    await updatePassword(input, session)
    const nextSession = await getInitialSession()
    setSession(nextSession)
    return await loadProfile(nextSession)
  }, [loadProfile, session])

  const resetRecoveredPassword = useCallback(async (input: ChangePasswordInput) => {
    setError(null)
    if (!session || !passwordRecoveryRef.current) {
      throw new Error(
        'Este link de recuperação é inválido ou expirou. Solicite um novo link.',
      )
    }

    if (needsPasswordChange(session.user)) {
      await updatePassword(input, session)
    } else {
      await updateRecoveredPassword(input)
    }

    const nextSession = await getInitialSession()
    setSession(nextSession)
    setPasswordRecoveryMode(false)
    try {
      await loadProfile(nextSession)
    } catch (caught) {
      setError(friendlyErrorMessage(caught, USER_MESSAGES.actionError))
    }
  }, [loadProfile, session, setPasswordRecoveryMode])

  const recoverPassword = useCallback(async (input: ForgotPasswordInput) => {
    setError(null)
    await requestPasswordReset(input)
  }, [])

  const logout = useCallback(async () => {
    setError(null)
    await signOut()
    setPasswordRecoveryMode(false)
    profileCacheRef.current.clear()
    setSession(null)
    setProfile(null)
  }, [setPasswordRecoveryMode])

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
      isPasswordRecovery,
      error,
      changePassword,
      resetRecoveredPassword,
      login,
      recoverPassword,
      logout,
      refreshProfile,
    }),
    [
      changePassword,
      error,
      isPasswordRecovery,
      loading,
      login,
      logout,
      profile,
      profileLoading,
      recoverPassword,
      refreshProfile,
      resetRecoveredPassword,
      requiresPasswordChange,
      session,
    ],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
