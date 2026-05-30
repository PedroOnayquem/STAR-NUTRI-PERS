import type { NutritionistRecord, ProfileSummary } from '../features/clinical/types'
import { getAppConfig } from './runtimeConfig'

const NUTRITIONIST_AVATAR_BUCKET = 'nutritionist-avatars'
const PUBLIC_OBJECT_PREFIX = `/storage/v1/object/public/${NUTRITIONIST_AVATAR_BUCKET}/`
const BUCKET_PATH_PREFIX = `/${NUTRITIONIST_AVATAR_BUCKET}/`

export function nutritionistAvatarUrl(
  nutritionist?: NutritionistRecord | null,
  profile?: ProfileSummary | null,
) {
  return resolveNutritionistAvatarUrl(
    nutritionist?.avatar_path ||
      nutritionist?.logo_path ||
      nutritionist?.avatar_url ||
      nutritionist?.logo_url ||
      profile?.avatar_url ||
      null,
  )
}

export function resolveNutritionistAvatarUrl(value?: string | null) {
  const rawValue = value?.trim()
  if (!rawValue) return null

  const supabaseUrl = getAppConfig('VITE_SUPABASE_URL')?.replace(/\/$/, '')

  if (rawValue.startsWith('blob:') || rawValue.startsWith('data:')) {
    return rawValue
  }

  if (rawValue.startsWith('http://') || rawValue.startsWith('https://')) {
    try {
      const parsed = new URL(rawValue)
      const publicPathIndex = parsed.pathname.indexOf(PUBLIC_OBJECT_PREFIX)
      if (publicPathIndex >= 0 && supabaseUrl) {
        const objectPath = parsed.pathname.slice(publicPathIndex + PUBLIC_OBJECT_PREFIX.length)
        return publicStorageUrl(objectPath, supabaseUrl)
      }

      const bucketPathIndex = parsed.pathname.indexOf(BUCKET_PATH_PREFIX)
      if (bucketPathIndex >= 0 && supabaseUrl) {
        const objectPath = parsed.pathname.slice(bucketPathIndex + BUCKET_PATH_PREFIX.length)
        return publicStorageUrl(objectPath, supabaseUrl)
      }
    } catch {
      return rawValue
    }

    return rawValue
  }

  const objectPath = rawValue.startsWith(`${NUTRITIONIST_AVATAR_BUCKET}/`)
    ? rawValue.slice(NUTRITIONIST_AVATAR_BUCKET.length + 1)
    : rawValue

  return publicStorageUrl(objectPath, supabaseUrl)
}

function publicStorageUrl(path: string, supabaseUrl?: string) {
  if (!supabaseUrl) return null
  const safePath = path
    .split('/')
    .filter(Boolean)
    .map(encodeURIComponent)
    .join('/')

  return `${supabaseUrl}/storage/v1/object/public/${NUTRITIONIST_AVATAR_BUCKET}/${safePath}`
}
