import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Bell, Check, Clock3 } from 'lucide-react'
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { Badge } from '../ui/Badge'
import { useAuth } from '../../features/auth/useAuth'
import {
  getNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from '../../features/clinical/services/clinicalDataService'
import type { NotificationRecord } from '../../features/clinical/types'
import { supabase } from '../../lib/supabase'
import { cn } from '../../lib/utils'

export function NotificationBell() {
  const { profile } = useAuth()
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const [toast, setToast] = useState<NotificationRecord | null>(null)
  const popoverRef = useRef<HTMLDivElement>(null)
  const rootRef = useRef<HTMLDivElement>(null)

  const query = useQuery({
    queryKey: ['notifications', profile?.id],
    queryFn: getNotifications,
    enabled: profile?.role === 'patient',
  })
  const notifications = query.data ?? []
  const unreadCount = query.data?.filter((notification) => !notification.read).length ?? 0

  const markReadMutation = useMutation({
    mutationFn: markNotificationRead,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notifications', profile?.id] }),
  })
  const markAllMutation = useMutation({
    mutationFn: markAllNotificationsRead,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notifications', profile?.id] }),
  })

  useEffect(() => {
    if (!open) return

    function handlePointerDown(event: PointerEvent) {
      const target = event.target as Node
      if (popoverRef.current?.contains(target) || rootRef.current?.contains(target)) {
        return
      }
      setOpen(false)
    }

    document.addEventListener('pointerdown', handlePointerDown)
    return () => document.removeEventListener('pointerdown', handlePointerDown)
  }, [open])

  useEffect(() => {
    const client = supabase
    if (!client || profile?.role !== 'patient' || !profile.id) return

    const channel = client
      .channel(`patient-sync-${profile.id}`)
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          filter: `user_id=eq.${profile.id}`,
          schema: 'public',
          table: 'notifications',
        },
        (payload) => {
          const notification = payload.new as NotificationRecord
          setToast(notification)
          queryClient.invalidateQueries({ queryKey: ['notifications', profile.id] })
          window.setTimeout(() => setToast(null), 4200)
        },
      )
      .on(
        'postgres_changes',
        {
          event: '*',
          filter: `patient_user_id=eq.${profile.id}`,
          schema: 'public',
          table: 'patient_appointments',
        },
        () => {
          queryClient.invalidateQueries({ queryKey: ['patient-context'] })
        },
      )
      .subscribe()

    return () => {
      client.removeChannel(channel)
    }
  }, [profile, queryClient])

  if (profile?.role !== 'patient') {
    return null
  }

  return (
    <div className="relative" ref={rootRef}>
      {toast && (
        <div className="fixed right-4 top-20 z-[90] w-[min(24rem,calc(100vw-2rem))] rounded-2xl border border-cyan-300/20 bg-[#07111f]/95 p-4 text-slate-100 shadow-[0_24px_80px_rgba(2,6,23,0.48)] backdrop-blur-xl">
          <p className="text-sm font-black">{toast.title}</p>
          <p className="mt-1 text-sm leading-6 text-slate-300">{toast.message}</p>
        </div>
      )}

      <Button
        aria-label="Notificações"
        onClick={() => setOpen((current) => !current)}
        size="icon"
        type="button"
        variant="secondary"
      >
        <Bell size={18} />
        {unreadCount > 0 && (
          <span className="absolute -right-1 -top-1 grid min-h-5 min-w-5 place-items-center rounded-full bg-emerald-500 px-1 text-[11px] font-black text-white shadow-[0_8px_22px_rgba(16,185,129,0.38)]">
            {unreadCount}
          </span>
        )}
      </Button>

      {open && (
        <div ref={popoverRef}>
          <Card
            className="absolute right-0 top-12 z-[70] w-[min(24rem,calc(100vw-2rem))] overflow-hidden p-0"
            variant="glass"
          >
          <div className="flex items-center justify-between gap-3 border-b border-slate-200/80 p-4 dark:border-white/10">
            <div>
              <h2 className="font-black">Notificações</h2>
              <p className="text-xs text-slate-500 dark:text-slate-400">
                Agenda e avisos do acompanhamento.
              </p>
            </div>
            {unreadCount > 0 && (
              <Button
                disabled={markAllMutation.isPending}
                onClick={() => markAllMutation.mutate()}
                size="sm"
                type="button"
                variant="secondary"
              >
                <Check size={15} />
                Ler tudo
              </Button>
            )}
          </div>

          <div className="premium-scrollbar max-h-96 overflow-y-auto">
            {notifications.length === 0 ? (
              <div className="p-5 text-sm text-slate-500 dark:text-slate-400">
                Nenhuma notificação por enquanto.
              </div>
            ) : (
              notifications.map((notification) => (
                <button
                  className={cn(
                    'block w-full border-b border-slate-100 p-4 text-left transition last:border-b-0 dark:border-white/10',
                    notification.read
                      ? 'hover:bg-white/[0.03]'
                      : 'bg-cyan-400/5 hover:bg-cyan-400/10',
                  )}
                  key={notification.id}
                  onClick={() => {
                    if (!notification.read) {
                      markReadMutation.mutate(notification.id)
                    }
                  }}
                  type="button"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="font-bold">{notification.title}</p>
                      <p className="mt-1 text-sm leading-6 text-slate-500 dark:text-slate-400">
                        {notification.message}
                      </p>
                    </div>
                    {!notification.read && <Badge tone="green">Novo</Badge>}
                  </div>
                  <p className="mt-2 inline-flex items-center gap-1.5 text-xs font-semibold text-slate-400">
                    <Clock3 size={13} />
                    {formatRelative(notification.created_at)}
                  </p>
                </button>
              ))
            )}
          </div>
          </Card>
        </div>
      )}
    </div>
  )
}

function formatRelative(value: string) {
  const diffMs = Date.now() - new Date(value).getTime()
  const minutes = Math.max(1, Math.round(diffMs / 60000))
  if (minutes < 60) return `há ${minutes} min`
  const hours = Math.round(minutes / 60)
  if (hours < 24) return `há ${hours}h`
  const days = Math.round(hours / 24)
  return `há ${days} dias`
}
