import { supabase } from '../../../lib/supabase'
import type { AuthProfile } from '../types'

type ProfileRow = {
  id: string
  full_name: string
  email: string
  role: 'admin' | 'nutritionist' | 'patient'
  is_active: boolean | null
  avatar_url?: string | null
  phone?: string | null
}

export async function getCurrentProfile(userId: string): Promise<AuthProfile | null> {
  if (!supabase) {
    throw new Error('Supabase nao configurado. Confira o arquivo .env.')
  }

  const { data, error } = await supabase
    .from('profiles')
    .select('id, full_name, email, role, is_active, avatar_url, phone')
    .eq('id', userId)
    .maybeSingle<ProfileRow>()

  if (error) {
    throw new Error(error.message)
  }

  if (!data || data.is_active === false) {
    return null
  }

  return {
    id: data.id,
    fullName: data.full_name,
    email: data.email,
    role: data.role,
    isActive: data.is_active ?? true,
    avatarUrl: data.avatar_url,
    phone: data.phone,
  }
}
