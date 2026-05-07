import type { ReactNode } from 'react'
import { Card } from './Card'

type StatCardProps = {
  icon: ReactNode
  label: string
  value: string | number
  caption: string
}

export function StatCard({ icon, label, value, caption }: StatCardProps) {
  return (
    <Card className="group p-5 hover:-translate-y-1 hover:shadow-[0_22px_70px_rgba(15,23,42,0.10)]">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-slate-500 dark:text-slate-400">
            {label}
          </p>
          <strong className="mt-2 block text-3xl font-black tracking-tight text-slate-950 dark:text-white">
            {value}
          </strong>
          <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
            {caption}
          </p>
        </div>
        <div className="rounded-xl border border-emerald-200/70 bg-emerald-50 p-2.5 text-emerald-700 shadow-sm transition group-hover:scale-105 dark:border-emerald-400/20 dark:bg-emerald-400/10 dark:text-emerald-300">
          {icon}
        </div>
      </div>
    </Card>
  )
}
