import { useEffect, useState } from 'react'
import type { NutritionistRecord, ProfileSummary } from '../../features/clinical/types'
import { nutritionistAvatarUrl } from '../../lib/storageImages'
import { cn } from '../../lib/utils'

type NutritionistAvatarProps = {
  className?: string
  nutritionist?: NutritionistRecord | null
  profile?: ProfileSummary | null
}

export function NutritionistAvatar({
  className,
  nutritionist,
  profile,
}: NutritionistAvatarProps) {
  const imageUrl = nutritionistAvatarUrl(nutritionist, profile)
  const [imageFailed, setImageFailed] = useState(false)
  const name =
    nutritionist?.professional_name ||
    profile?.full_name ||
    nutritionist?.clinic_name ||
    'Nutricionista'

  useEffect(() => {
    setImageFailed(false)
  }, [imageUrl])

  return (
    <div
      className={cn(
        'flex h-14 w-14 shrink-0 items-center justify-center overflow-hidden rounded-2xl border border-emerald-200/70 bg-gradient-to-br from-emerald-50 to-cyan-50 text-sm font-black text-emerald-800 shadow-sm dark:border-emerald-400/20 dark:from-emerald-400/15 dark:to-cyan-400/10 dark:text-emerald-100',
        className,
      )}
    >
      {imageUrl && !imageFailed ? (
        <img
          alt={name}
          className="h-full w-full object-cover"
          onError={() => setImageFailed(true)}
          src={imageUrl}
        />
      ) : (
        <span>{initials(name)}</span>
      )}
    </div>
  )
}

function initials(value: string) {
  return value
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join('') || 'N'
}
