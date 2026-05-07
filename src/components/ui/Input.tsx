import type { InputHTMLAttributes, TextareaHTMLAttributes } from 'react'
import { cn } from '../../lib/utils'

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        'h-11 w-full rounded-xl border border-slate-200/80 bg-white/90 px-3.5 py-2 text-sm text-slate-950 shadow-sm outline-none transition-all duration-200 placeholder:text-slate-400 hover:border-slate-300 focus:border-emerald-500 focus:ring-4 focus:ring-emerald-500/10 dark:border-white/10 dark:bg-white/[0.04] dark:text-white dark:placeholder:text-slate-500 dark:hover:border-white/20 dark:focus:border-emerald-400 dark:focus:ring-emerald-400/10',
        className,
      )}
      {...props}
    />
  )
}

export function Textarea({
  className,
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={cn(
        'min-h-28 w-full rounded-xl border border-slate-200/80 bg-white/90 px-3.5 py-2.5 text-sm text-slate-950 shadow-sm outline-none transition-all duration-200 placeholder:text-slate-400 hover:border-slate-300 focus:border-emerald-500 focus:ring-4 focus:ring-emerald-500/10 dark:border-white/10 dark:bg-white/[0.04] dark:text-white dark:placeholder:text-slate-500 dark:hover:border-white/20 dark:focus:border-emerald-400 dark:focus:ring-emerald-400/10',
        className,
      )}
      {...props}
    />
  )
}
