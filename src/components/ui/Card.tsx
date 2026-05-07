import type { ReactNode } from 'react'
import { cn } from '../../lib/utils'

type CardProps = {
  children: ReactNode
  className?: string
  variant?: 'default' | 'glass' | 'flat'
}

export function Card({ children, className, variant = 'default' }: CardProps) {
  return (
    <div
      className={cn(
        'rounded-2xl transition-all duration-200',
        variant === 'default' &&
          'border border-slate-200/80 bg-white shadow-[0_18px_50px_rgba(15,23,42,0.06)] dark:border-white/10 dark:bg-slate-900/90 dark:shadow-none',
        variant === 'glass' &&
          'border border-white/60 bg-white/70 shadow-[0_24px_70px_rgba(15,23,42,0.10)] backdrop-blur-xl dark:border-white/10 dark:bg-white/[0.06]',
        variant === 'flat' &&
          'border border-slate-200/80 bg-slate-50/70 dark:border-white/10 dark:bg-white/[0.04]',
        className,
      )}
    >
      {children}
    </div>
  )
}
