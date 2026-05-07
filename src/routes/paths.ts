import type { UserRole } from '../features/auth/types'

export function getRolePath(role: UserRole) {
  const paths: Record<UserRole, string> = {
    admin: '/admin',
    nutritionist: '/nutritionist',
    patient: '/patient',
  }

  return paths[role]
}
