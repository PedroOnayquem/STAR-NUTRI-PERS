import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom'
import {
  Activity,
  Bot,
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
import type { ReactNode } from 'react'
import { useAuth } from '../../features/auth/useAuth'
import { cn } from '../../lib/utils'
import { Button } from '../ui/Button'
import { Badge } from '../ui/Badge'

const navByRole = {
  admin: [
    { to: '/admin', label: 'Command center', icon: <Shield size={18} />, preload: () => import('../../pages/AdminPage') },
    { to: '/admin/users', label: 'Usuarios', icon: <Users size={18} />, preload: () => import('../../pages/AdminPage') },
  ],
  nutritionist: [
    { to: '/nutritionist', label: 'Dashboard', icon: <LayoutDashboard size={18} />, preload: () => import('../../pages/nutritionist/NutritionistDashboardPage') },
    { to: '/nutritionist/patients', label: 'Pacientes', icon: <Users size={18} />, preload: () => import('../../pages/nutritionist/PatientsPage') },
    { to: '/nutritionist/chat', label: 'Chat IA', icon: <Bot size={18} />, preload: () => import('../../pages/nutritionist/NutritionistChatPage') },
  ],
  patient: [
    { to: '/patient', label: 'Dashboard', icon: <LayoutDashboard size={18} />, preload: () => import('../../pages/patient/PatientWorkspacePage') },
    { to: '/patient/diet', label: 'Minha dieta', icon: <Activity size={18} />, preload: () => import('../../pages/patient/PatientWorkspacePage') },
    { to: '/patient/workout', label: 'Meu treino', icon: <Activity size={18} />, preload: () => import('../../pages/patient/PatientWorkspacePage') },
    { to: '/patient/metrics', label: 'Metricas', icon: <Activity size={18} />, preload: () => import('../../pages/patient/PatientWorkspacePage') },
    { to: '/patient/evolution', label: 'Evolucao', icon: <Activity size={18} />, preload: () => import('../../pages/patient/PatientWorkspacePage') },
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

  async function handleLogout() {
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="min-h-screen bg-slate-50 text-slate-950 dark:bg-slate-950 dark:text-white">
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-72 border-r border-slate-200/70 bg-white/80 px-4 py-5 shadow-[18px_0_70px_rgba(15,23,42,0.06)] backdrop-blur-xl dark:border-white/10 dark:bg-slate-950/70 lg:block">
        <Brand />

        <div className="mt-6 rounded-2xl border border-emerald-200/70 bg-gradient-to-br from-emerald-50 to-cyan-50 p-4 dark:border-emerald-400/20 dark:from-emerald-400/10 dark:to-cyan-400/10">
          <div className="flex items-center gap-2 text-emerald-700 dark:text-emerald-300">
            <Sparkles size={16} />
            <p className="text-xs font-black uppercase">Workspace ativo</p>
          </div>
          <p className="mt-2 text-sm font-bold">{profile?.fullName}</p>
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            {profile?.role}
          </p>
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
              <div className="hidden min-w-80 items-center gap-3 rounded-2xl border border-slate-200/80 bg-white/80 px-3 py-2 text-slate-500 shadow-sm dark:border-white/10 dark:bg-white/[0.04] dark:text-slate-400 md:flex">
                <Search size={17} />
                <span className="text-sm">Buscar pacientes, metricas ou planos</span>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Badge tone="green">Online</Badge>
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
      <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-gradient-to-br from-emerald-400 via-teal-400 to-cyan-400 text-sm font-black text-slate-950 shadow-[0_14px_40px_rgba(16,185,129,0.30)]">
        SN
      </div>
      {!compact && (
        <div>
          <p className="text-base font-black">Star Nutri</p>
          <p className="text-xs font-medium text-slate-500 dark:text-slate-400">
            Nutrition intelligence
          </p>
        </div>
      )}
      {compact && <UserRound className="text-slate-500" size={20} />}
    </div>
  )
}
