import type { ReactNode } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import type { UserRole } from '../features/auth/types'
import { useAuth } from '../features/auth/useAuth'
import { changePasswordPath, getRolePath } from './paths'

export function PublicOnlyRoute({ children }: { children: ReactNode }) {
  const { loading, profile, profileLoading, requiresPasswordChange, session } = useAuth()

  if (loading || profileLoading) {
    return <FullPageLoading />
  }

  if (session) {
    if (requiresPasswordChange) {
      return <Navigate replace to={changePasswordPath} />
    }

    if (profile) {
      return <Navigate replace to={getRolePath(profile.role)} />
    }

    return <Navigate replace to="/auth/profile-missing" />
  }

  return children
}

export function ProtectedRoute({ allowedRoles }: { allowedRoles?: UserRole[] }) {
  const { loading, profile, profileLoading, requiresPasswordChange, session } = useAuth()
  const location = useLocation()

  if (loading || profileLoading) {
    return <FullPageLoading />
  }

  if (!session) {
    return <Navigate replace state={{ from: location }} to="/login" />
  }

  if (requiresPasswordChange) {
    return <Navigate replace to={changePasswordPath} />
  }

  if (!profile) {
    return <Navigate replace to="/auth/profile-missing" />
  }

  if (allowedRoles && !allowedRoles.includes(profile.role)) {
    return <Navigate replace to={getRolePath(profile.role)} />
  }

  return <Outlet />
}

export function RoleRedirect() {
  const { loading, profile, profileLoading, requiresPasswordChange, session } = useAuth()

  if (loading || profileLoading) {
    return <FullPageLoading />
  }

  if (!session) {
    return <Navigate replace to="/login" />
  }

  if (requiresPasswordChange) {
    return <Navigate replace to={changePasswordPath} />
  }

  if (!profile) {
    return <Navigate replace to="/auth/profile-missing" />
  }

  return <Navigate replace to={getRolePath(profile.role)} />
}

export function PasswordChangeRoute() {
  const { loading, profile, profileLoading, requiresPasswordChange, session } = useAuth()

  if (loading || profileLoading) {
    return <FullPageLoading />
  }

  if (!session) {
    return <Navigate replace to="/login" />
  }

  if (!requiresPasswordChange) {
    if (!profile) {
      return <Navigate replace to="/auth/profile-missing" />
    }

    return <Navigate replace to={getRolePath(profile.role)} />
  }

  return <Outlet />
}

export function FullPageLoading() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 text-slate-950 dark:bg-slate-950 dark:text-white">
      <div className="text-center">
        <div className="mx-auto h-10 w-10 animate-spin rounded-full border-4 border-slate-200 border-t-emerald-600 dark:border-slate-800 dark:border-t-emerald-400" />
        <p className="mt-4 text-sm font-semibold text-slate-500 dark:text-slate-400">
          Carregando Star Nutri...
        </p>
      </div>
    </main>
  )
}
