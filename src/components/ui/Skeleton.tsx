import { cn } from '../../lib/utils'

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        'animate-pulse rounded-xl bg-slate-200/80 dark:bg-white/10',
        className,
      )}
    />
  )
}

export function PageSkeleton() {
  return (
    <div className="space-y-5">
      <Skeleton className="h-10 w-72" />
      <div className="grid gap-4 md:grid-cols-3">
        <Skeleton className="h-32" />
        <Skeleton className="h-32" />
        <Skeleton className="h-32" />
      </div>
      <Skeleton className="h-96" />
    </div>
  )
}
