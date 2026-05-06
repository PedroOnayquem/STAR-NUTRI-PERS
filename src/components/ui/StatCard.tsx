import type { ReactNode } from 'react'
import { Card } from './Card'

type StatCardProps = {
  icon: ReactNode
  label: string
  value: string
  caption: string
}

export function StatCard({ icon, label, value, caption }: StatCardProps) {
  return (
    <Card className="p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium text-slate-500 dark:text-slate-400">
            {label}
          </p>
          <strong className="mt-2 block text-2xl font-bold text-slate-950 dark:text-white">
            {value}
          </strong>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            {caption}
          </p>
        </div>
        <div className="rounded-lg bg-emerald-50 p-2.5 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
          {icon}
        </div>
      </div>
    </Card>
  )
}
