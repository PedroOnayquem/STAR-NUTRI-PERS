import type { ReactNode } from 'react'
import {
  Activity,
  Bot,
  Dumbbell,
  LayoutDashboard,
  LogOut,
  Moon,
  Shield,
  Sun,
  Users,
  Utensils,
} from 'lucide-react'
import type { Profile, UserRole } from '../../types'
import { Button } from '../ui/Button'

type AppShellProps = {
  children: ReactNode
  profile: Profile
  activeView: string
  onNavigate: (view: string) => void
  onLogout: () => void
  isDark: boolean
  onToggleTheme: () => void
}

const navByRole: Record<UserRole, Array<{ id: string; label: string; icon: ReactNode }>> = {
  admin: [
    { id: 'admin', label: 'Admin', icon: <Shield size={18} /> },
    { id: 'patients', label: 'Pacientes', icon: <Users size={18} /> },
  ],
  nutritionist: [
    { id: 'dashboard', label: 'Dashboard', icon: <LayoutDashboard size={18} /> },
    { id: 'patients', label: 'Pacientes', icon: <Users size={18} /> },
    { id: 'diet', label: 'Dietas', icon: <Utensils size={18} /> },
    { id: 'workout', label: 'Treinos', icon: <Dumbbell size={18} /> },
    { id: 'metrics', label: 'Métricas', icon: <Activity size={18} /> },
    { id: 'chat', label: 'IA', icon: <Bot size={18} /> },
  ],
  patient: [
    { id: 'patient-home', label: 'Meu plano', icon: <LayoutDashboard size={18} /> },
    { id: 'patient-metrics', label: 'Métricas', icon: <Activity size={18} /> },
    { id: 'patient-chat', label: 'Chat IA', icon: <Bot size={18} /> },
  ],
}

export function AppShell({
  children,
  profile,
  activeView,
  onNavigate,
  onLogout,
  isDark,
  onToggleTheme,
}: AppShellProps) {
  const navItems = navByRole[profile.role]

  return (
    <div className="min-h-screen bg-slate-50 text-slate-950 dark:bg-slate-950 dark:text-white">
      <aside className="fixed inset-y-0 left-0 z-20 hidden w-64 border-r border-slate-200 bg-white px-4 py-5 dark:border-slate-800 dark:bg-slate-900 lg:block">
        <Brand />

        <nav className="mt-8 space-y-1">
          {navItems.map((item) => (
            <button
              className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-semibold transition ${
                activeView === item.id
                  ? 'bg-emerald-50 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300'
                  : 'text-slate-600 hover:bg-slate-100 hover:text-slate-950 dark:text-slate-300 dark:hover:bg-slate-800 dark:hover:text-white'
              }`}
              key={item.id}
              onClick={() => onNavigate(item.id)}
              type="button"
            >
              {item.icon}
              {item.label}
            </button>
          ))}
        </nav>
      </aside>

      <div className="lg:pl-64">
        <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/85 px-4 py-3 backdrop-blur dark:border-slate-800 dark:bg-slate-900/85 sm:px-6">
          <div className="flex items-center justify-between gap-4">
            <div className="lg:hidden">
              <Brand compact />
            </div>

            <div className="hidden lg:block">
              <p className="text-sm font-medium text-slate-500 dark:text-slate-400">
                Logado como
              </p>
              <p className="text-sm font-bold text-slate-950 dark:text-white">
                {profile.fullName}
              </p>
            </div>

            <div className="flex items-center gap-2">
              <Button
                aria-label="Alternar tema"
                className="h-10 w-10 px-0"
                onClick={onToggleTheme}
                title="Alternar tema"
                type="button"
                variant="secondary"
              >
                {isDark ? <Sun size={18} /> : <Moon size={18} />}
              </Button>
              <Button onClick={onLogout} type="button" variant="secondary">
                <LogOut size={18} />
                <span className="hidden sm:inline">Sair</span>
              </Button>
            </div>
          </div>

          <div className="mt-3 flex gap-2 overflow-x-auto pb-1 lg:hidden">
            {navItems.map((item) => (
              <button
                className={`inline-flex shrink-0 items-center gap-2 rounded-lg px-3 py-2 text-sm font-semibold ${
                  activeView === item.id
                    ? 'bg-emerald-600 text-white'
                    : 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-200'
                }`}
                key={item.id}
                onClick={() => onNavigate(item.id)}
                type="button"
              >
                {item.icon}
                {item.label}
              </button>
            ))}
          </div>
        </header>

        <main className="px-4 py-6 sm:px-6 lg:px-8">{children}</main>
      </div>
    </div>
  )
}

function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <div className="flex items-center gap-3">
      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-600 text-sm font-black text-white">
        SN
      </div>
      {!compact && (
        <div>
          <p className="text-base font-black text-slate-950 dark:text-white">
            Star Nutri
          </p>
          <p className="text-xs font-medium text-slate-500 dark:text-slate-400">
            Nutrição com IA
          </p>
        </div>
      )}
    </div>
  )
}
