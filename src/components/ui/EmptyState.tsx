import type { ReactNode } from 'react'
import { cn } from '../../lib/utils'

export function EmptyState({
  action,
  description,
  icon,
  title,
  className,
}: {
  action?: ReactNode
  description: string
  icon?: ReactNode
  title: string
  className?: string
}) {
  return (
    <div
      className={cn(
        'flex min-h-56 flex-col items-center justify-center rounded-2xl border border-dashed border-slate-300 bg-white/60 p-8 text-center dark:border-white/15 dark:bg-white/[0.03]',
        className,
      )}
    >
      {icon && (
        <div className="mb-4 rounded-2xl bg-slate-100 p-3 text-slate-600 dark:bg-white/10 dark:text-slate-300">
          {icon}
        </div>
      )}
      <h3 className="text-base font-black">{title}</h3>
      <p className="mt-2 max-w-md text-sm leading-6 text-slate-500 dark:text-slate-400">
        {description}
      </p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  )
}
