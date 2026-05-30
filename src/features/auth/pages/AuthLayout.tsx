import { Activity, Bot, Moon, ShieldCheck, Sparkles, Sun } from 'lucide-react'
import type { ReactNode } from 'react'
import { Logo } from '../../../components/Logo'
import { Button } from '../../../components/ui/Button'

export function AuthLayout({
  children,
  isDark,
  onToggleTheme,
}: {
  children: ReactNode
  isDark: boolean
  onToggleTheme: () => void
}) {
  return (
    <main className="min-h-screen overflow-hidden bg-slate-50 text-slate-950 dark:bg-slate-950 dark:text-white">
      <div className="grid min-h-screen lg:grid-cols-[1.05fr_0.95fr]">
        <section className="relative hidden min-h-screen flex-col justify-between overflow-hidden bg-slate-950 px-10 py-8 text-white lg:flex">
          <div className="absolute inset-0 bg-[linear-gradient(120deg,rgba(16,185,129,0.18),transparent_35%),radial-gradient(circle_at_78%_18%,rgba(6,182,212,0.20),transparent_28%)]" />
          <div className="absolute inset-x-10 top-24 h-px bg-gradient-to-r from-transparent via-white/20 to-transparent" />

          <div className="relative z-10 flex items-center justify-between gap-4">
            <Brand />
            <Button
              aria-label="Alternar tema"
              className="border-white/15 bg-white/10 text-white hover:bg-white/15 dark:border-white/15 dark:bg-white/10"
              onClick={onToggleTheme}
              size="icon"
              title="Alternar tema"
              type="button"
              variant="secondary"
            >
              {isDark ? <Sun size={18} /> : <Moon size={18} />}
            </Button>
          </div>

          <div className="relative z-10 max-w-2xl">
            <span className="inline-flex items-center gap-2 rounded-full border border-emerald-300/20 bg-emerald-400/10 px-3 py-1 text-sm font-bold text-emerald-200 shadow-2xl shadow-emerald-950/40 backdrop-blur">
              <Sparkles size={14} />
              Plataforma inteligente para nutrição
            </span>
            <h1 className="mt-6 text-5xl font-black leading-[1.02] tracking-normal xl:text-7xl">
              Nutrição clínica com dados, clareza e inteligência.
            </h1>
            <p className="mt-6 max-w-xl text-lg leading-8 text-slate-300">
              Uma experiência premium para nutricionistas acompanharem pacientes,
              planos, métricas e evolução com mais segurança.
            </p>
          </div>

          <div className="relative z-10 grid gap-3 xl:grid-cols-3">
            {[
              { icon: <ShieldCheck size={18} />, label: 'Acesso seguro' },
              { icon: <Activity size={18} />, label: 'Métricas claras' },
              { icon: <Bot size={18} />, label: 'Assistente integrado' },
            ].map((item) => (
              <div
                className="rounded-2xl border border-white/10 bg-white/[0.06] p-4 shadow-2xl shadow-black/20 backdrop-blur"
                key={item.label}
              >
                <div className="text-emerald-300">{item.icon}</div>
                <p className="mt-3 text-sm font-bold">{item.label}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="relative flex min-h-screen items-center justify-center px-5 py-8 sm:px-8">
          <div className="absolute right-5 top-5 lg:hidden">
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
          </div>
          <div className="w-full max-w-md">
            <div className="mb-8 flex justify-center lg:hidden">
              <Brand dark />
            </div>
            {children}
          </div>
        </section>
      </div>
    </main>
  )
}

function Brand({ dark = false }: { dark?: boolean }) {
  return (
    <div className="flex items-center gap-3">
      <Logo className="h-16 w-auto max-w-[220px]" showText={dark} />
    </div>
  )
}
