import type { ReactNode } from 'react'
import { cn } from '../../lib/utils'

type BadgeProps = {
  children: ReactNode
  tone?: 'green' | 'blue' | 'amber' | 'red' | 'slate'
}

const tones = {
  green:
    'border-emerald-200/80 bg-emerald-50 text-emerald-700 dark:border-emerald-400/20 dark:bg-emerald-400/10 dark:text-emerald-300',
  blue: 'border-cyan-200/80 bg-cyan-50 text-cyan-700 dark:border-cyan-400/20 dark:bg-cyan-400/10 dark:text-cyan-300',
  amber:
    'border-amber-200/80 bg-amber-50 text-amber-700 dark:border-amber-400/20 dark:bg-amber-400/10 dark:text-amber-300',
  red: 'border-rose-200/80 bg-rose-50 text-rose-700 dark:border-rose-400/20 dark:bg-rose-400/10 dark:text-rose-300',
  slate:
    'border-slate-200/80 bg-slate-100/80 text-slate-700 dark:border-white/10 dark:bg-white/10 dark:text-slate-300',
}

export function Badge({ children, tone = 'slate' }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold shadow-sm backdrop-blur',
        tones[tone],
      )}
    >
      {children}
    </span>
  )
}
