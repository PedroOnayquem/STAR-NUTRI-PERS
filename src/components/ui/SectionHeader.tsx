import type { ReactNode } from 'react'

export function SectionHeader({
  actions,
  description,
  eyebrow,
  title,
}: {
  actions?: ReactNode
  description?: string
  eyebrow?: ReactNode
  title: string
}) {
  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
      <div>
        {eyebrow && <div className="mb-3">{eyebrow}</div>}
        <h1 className="text-3xl font-black tracking-tight sm:text-4xl">{title}</h1>
        {description && (
          <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500 dark:text-slate-400">
            {description}
          </p>
        )}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  )
}
