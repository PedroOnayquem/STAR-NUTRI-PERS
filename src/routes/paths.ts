import type { UserRole } from '../features/auth/types'

export const changePasswordPath = '/auth/change-password'
export const resetPasswordPath = '/auth/reset-password'

export function getRolePath(role: UserRole) {
  const paths: Record<UserRole, string> = {
    admin: '/admin',
    nutritionist: '/nutritionist',
    patient: '/patient',
  }

  return paths[role]
}
