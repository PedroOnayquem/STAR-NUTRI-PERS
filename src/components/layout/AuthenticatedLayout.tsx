import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom'
import {
  Activity,
  Bot,
  BookOpen,
  CalendarDays,
  ChevronRight,
  LayoutDashboard,
  LogOut,
  Moon,
  Search,
  Shield,
  Sparkles,
  Sun,
  UserRound,
  Users,
} from 'lucide-react'
import { useEffect, useState, type ReactNode } from 'react'
import { useAuth } from '../../features/auth/useAuth'
import { cn } from '../../lib/utils'
import { Button } from '../ui/Button'
import { Badge } from '../ui/Badge'
import { NotificationBell } from '../notifications/NotificationBell'
import { PwaInstallButton } from '../pwa/PwaInstallButton'
import { Logo } from '../Logo'
import { resolveNutritionistAvatarUrl } from '../../lib/storageImages'

const navByRole = {
  admin: [
    { to: '/admin', label: 'Painel administrativo', icon: <Shield size={18} />, preload: () => import('../../pages/AdminPage') },
    { to: '/admin/users', label: 'Usuários', icon: <Users size={18} />, preload: () => import('../../pages/AdminPage') },
  ],
  nutritionist: [
    { to: '/nutritionist', label: 'Dashboard', icon: <LayoutDashboard size={18} />, preload: () => import('../../pages/nutritionist/NutritionistDashboardPage') },
    { to: '/nutritionist/patients', label: 'Pacientes', icon: <Users size={18} />, preload: () => import('../../pages/nutritionist/PatientsPage') },
    { to: '/nutritionist/taco', label: 'Tabela TACO', icon: <BookOpen size={18} />, preload: () => import('../../pages/nutritionist/TacoPage') },
    { to: '/nutritionist/chat', label: 'Chat IA', icon: <Bot size={18} />, preload: () => import('../../pages/nutritionist/NutritionistChatPage') },
    { to: '/nutritionist/profile', label: 'Perfil', icon: <UserRound size={18} />, preload: () => import('../../pages/nutritionist/NutritionistProfilePage') },
  ],
  patient: [
    { to: '/patient', label: 'Dashboard', icon: <LayoutDashboard size={18} />, preload: () => import('../../pages/patient/PatientWorkspacePage') },
    { to: '/patient/diet', label: 'Minha dieta', icon: <Activity size={18} />, preload: () => import('../../pages/patient/PatientWorkspacePage') },
    { to: '/patient/workout', label: 'Meu treino', icon: <Activity size={18} />, preload: () => import('../../pages/patient/PatientWorkspacePage') },
    { to: '/patient/agenda', label: 'Agenda', icon: <CalendarDays size={18} />, preload: () => import('../../pages/patient/PatientWorkspacePage') },
    { to: '/patient/metrics', label: 'Métricas', icon: <Activity size={18} />, preload: () => import('../../pages/patient/PatientWorkspacePage') },
    { to: '/patient/chat', label: 'Chat IA', icon: <Bot size={18} />, preload: () => import('../../pages/patient/PatientWorkspacePage') },
    { to: '/patient/profile', label: 'Perfil', icon: <UserRound size={18} />, preload: () => import('../../pages/patient/PatientWorkspacePage') },
  ],
}

export function AuthenticatedLayout({
  isDark,
  onToggleTheme,
}: {
  isDark: boolean
  onToggleTheme: () => void
}) {
  const { logout, profile } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const navItems = profile ? navByRole[profile.role] : []
  const hideGlobalSearch =
    profile?.role === 'patient' ||
    (profile?.role === 'nutritionist' && location.pathname === '/nutritionist')

  async function handleLogout() {
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-950 dark:bg-slate-950 dark:text-white">
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-72 border-r border-slate-200/70 bg-white/80 px-4 py-5 shadow-[18px_0_70px_rgba(15,23,42,0.06)] backdrop-blur-xl dark:border-white/10 dark:bg-slate-950/70 lg:block">
        <Brand />

        <div className="mt-6 rounded-2xl border border-emerald-200/70 bg-gradient-to-br from-emerald-50 to-cyan-50 p-4 dark:border-emerald-400/20 dark:from-emerald-400/10 dark:to-cyan-400/10">
          <div className="flex items-center gap-3">
            <ProfileAvatar imageUrl={profile?.avatarUrl} name={profile?.fullName} />
            <div className="min-w-0">
              <div className="flex items-center gap-2 text-emerald-700 dark:text-emerald-300">
                <Sparkles size={16} />
                <p className="text-xs font-black uppercase">Conta ativa</p>
              </div>
              <p className="mt-1 truncate text-sm font-bold">{profile?.fullName}</p>
              <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                {profile?.role}
              </p>
            </div>
          </div>
        </div>

        <nav className="mt-6 space-y-1.5">
          {navItems.map((item) => (
            <NavLink
              active={isNavItemActive(location.pathname, item.to, navItems)}
              icon={item.icon}
              key={item.to}
              label={item.label}
              onPreload={item.preload}
              to={item.to}
            />
          ))}
        </nav>
      </aside>

      <div className="lg:pl-72">
        <header className="sticky top-0 z-10 border-b border-slate-200/70 bg-slate-50/80 px-4 py-3 backdrop-blur-xl dark:border-white/10 dark:bg-slate-950/75 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className="lg:hidden">
                <Brand compact />
              </div>
              {!hideGlobalSearch && (
                <div className="hidden min-w-80 items-center gap-3 rounded-2xl border border-slate-200/80 bg-white/80 px-3 py-2 text-slate-500 shadow-sm dark:border-white/10 dark:bg-white/[0.04] dark:text-slate-400 md:flex">
                  <Search size={17} />
                  <span className="text-sm">Buscar pacientes, métricas ou planos</span>
                </div>
              )}
            </div>

            <div className="flex items-center gap-2">
              <Badge tone="green">Online</Badge>
              <PwaInstallButton />
              <NotificationBell />
              <Button
                aria-label="Alternar tema"
                onClick={onToggleTheme}
                size="icon"
                title="Alternar tema"
                type="button"
                variant="secondary"
              >
                {isDark ? <Sun size={18} /> : <Moon size={18} />}
              </Button>
              <Button onClick={handleLogout} type="button" variant="secondary">
                <LogOut size={18} />
                <span className="hidden sm:inline">Sair</span>
              </Button>
            </div>
          </div>

          <div className="mt-3 flex gap-2 overflow-x-auto pb-1 lg:hidden">
            {navItems.map((item) => (
              <Link
                className={cn(
                  'inline-flex shrink-0 items-center gap-2 rounded-xl px-3 py-2 text-sm font-semibold transition',
                  isNavItemActive(location.pathname, item.to, navItems)
                    ? 'bg-slate-950 text-white dark:bg-white dark:text-slate-950'
                    : 'bg-white text-slate-700 shadow-sm dark:bg-white/10 dark:text-slate-200',
                )}
                key={item.to}
                onFocus={item.preload}
                onMouseEnter={item.preload}
                to={item.to}
              >
                {item.icon}
                {item.label}
              </Link>
            ))}
          </div>
        </header>

        <main className="px-4 py-6 sm:px-6 lg:px-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

function isNavItemActive(
  pathname: string,
  currentTo: string,
  navItems: Array<{ to: string }>,
) {
  if (pathname === currentTo) {
    return true
  }

  if (!pathname.startsWith(`${currentTo}/`)) {
    return false
  }

  return !navItems.some((item) => {
    if (item.to === currentTo) {
      return false
    }

    const isMoreSpecific = item.to.startsWith(`${currentTo}/`)
    const matchesPath =
      pathname === item.to || pathname.startsWith(`${item.to}/`)

    return isMoreSpecific && matchesPath
  })
}

function NavLink({
  active,
  icon,
  label,
  onPreload,
  to,
}: {
  active: boolean
  icon: ReactNode
  label: string
  onPreload?: () => Promise<unknown>
  to: string
}) {
  return (
    <Link
      className={cn(
        'group flex w-full items-center justify-between rounded-2xl px-3 py-3 text-sm font-semibold transition-all duration-200',
        active
          ? 'bg-slate-950 text-white shadow-[0_16px_42px_rgba(15,23,42,0.22)] dark:bg-white dark:text-slate-950'
          : 'text-slate-600 hover:bg-slate-100 hover:text-slate-950 dark:text-slate-300 dark:hover:bg-white/10 dark:hover:text-white',
      )}
      onFocus={onPreload}
      onMouseEnter={onPreload}
      to={to}
    >
      <span className="flex items-center gap-3">
        {icon}
        {label}
      </span>
      <ChevronRight
        className={cn(
          'opacity-0 transition group-hover:opacity-100',
          active && 'opacity-100',
        )}
        size={15}
      />
    </Link>
  )
}

function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <div className="flex items-center gap-3">
      <Logo
        className={compact ? 'h-10 w-auto max-w-[140px]' : 'h-12 w-auto max-w-[180px]'}
        showText={!compact}
      />
    </div>
  )
}

function ProfileAvatar({
  imageUrl,
  name,
}: {
  imageUrl?: string | null
  name?: string | null
}) {
  const resolvedImageUrl = resolveNutritionistAvatarUrl(imageUrl)
  const [imageFailed, setImageFailed] = useState(false)

  useEffect(() => {
    setImageFailed(false)
  }, [resolvedImageUrl])

  return (
    <div className="flex h-12 w-12 shrink-0 items-center justify-center overflow-hidden rounded-2xl border border-white/60 bg-white/80 text-sm font-black text-emerald-800 shadow-sm dark:border-white/10 dark:bg-slate-950/50 dark:text-emerald-100">
      {resolvedImageUrl && !imageFailed ? (
        <img
          alt={name ?? 'Perfil'}
          className="h-full w-full object-cover"
          onError={() => setImageFailed(true)}
          src={resolvedImageUrl}
        />
      ) : (
        <span>{getInitials(name ?? 'Nutricionista')}</span>
      )}
    </div>
  )
}

function getInitials(value: string) {
  return value
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join('') || 'N'
}
