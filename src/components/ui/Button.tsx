import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import type { ButtonHTMLAttributes } from 'react'
import { cn } from '../../lib/utils'

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl text-sm font-semibold tracking-normal transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500/50 focus-visible:ring-offset-2 focus-visible:ring-offset-white disabled:pointer-events-none disabled:opacity-50 dark:focus-visible:ring-offset-slate-950 [&_svg]:pointer-events-none [&_svg]:shrink-0',
  {
    variants: {
      variant: {
        primary:
          'bg-slate-950 text-white shadow-[0_10px_30px_rgba(15,23,42,0.18)] hover:-translate-y-0.5 hover:bg-slate-800 hover:shadow-[0_16px_40px_rgba(15,23,42,0.22)] dark:bg-white dark:text-slate-950 dark:hover:bg-slate-200',
        secondary:
          'border border-slate-200/80 bg-white/85 text-slate-800 shadow-sm hover:-translate-y-0.5 hover:border-slate-300 hover:bg-white hover:shadow-md dark:border-white/10 dark:bg-white/5 dark:text-slate-100 dark:hover:bg-white/10',
        ghost:
          'text-slate-600 hover:bg-slate-100 hover:text-slate-950 dark:text-slate-300 dark:hover:bg-white/10 dark:hover:text-white',
        premium:
          'bg-gradient-to-r from-emerald-500 via-teal-500 to-cyan-500 text-white shadow-[0_16px_44px_rgba(16,185,129,0.28)] hover:-translate-y-0.5 hover:shadow-[0_18px_52px_rgba(20,184,166,0.34)]',
        destructive:
          'bg-rose-600 text-white shadow-sm hover:-translate-y-0.5 hover:bg-rose-700',
      },
      size: {
        sm: 'h-9 px-3',
        md: 'h-11 px-4',
        lg: 'h-12 px-5',
        icon: 'h-10 w-10 p-0',
      },
    },
    defaultVariants: {
      size: 'md',
      variant: 'primary',
    },
  },
)

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> &
  VariantProps<typeof buttonVariants> & {
    asChild?: boolean
  }

export function Button({ asChild, className, size, variant, ...props }: ButtonProps) {
  const Comp = asChild ? Slot : 'button'

  return <Comp className={cn(buttonVariants({ className, size, variant }))} {...props} />
}
