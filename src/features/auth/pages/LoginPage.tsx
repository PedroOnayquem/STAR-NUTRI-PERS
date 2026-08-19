import { ArrowRight, LockKeyhole, Mail } from 'lucide-react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useState, type FormEvent } from 'react'
import { Button } from '../../../components/ui/Button'
import { Card } from '../../../components/ui/Card'
import { Input } from '../../../components/ui/Input'
import { changePasswordPath, getRolePath } from '../../../routes/paths'
import type { LoginInput } from '../types'
import { useAuth } from '../useAuth'
import { validateLogin } from '../validation'

export function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { login } = useAuth()
  const redirectedFrom = (location.state as { from?: { pathname?: string } } | null)
    ?.from?.pathname
  const [form, setForm] = useState<LoginInput>({ email: '', password: '' })
  const [errors, setErrors] = useState<Partial<Record<keyof LoginInput, string>>>({})
  const [feedback, setFeedback] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const nextErrors = validateLogin(form)
    setErrors(nextErrors)
    setFeedback(null)

    if (Object.keys(nextErrors).length > 0) {
      return
    }

    setLoading(true)
    try {
      const result = await login(form)
      if (result.requiresPasswordChange) {
        navigate(changePasswordPath, { replace: true })
        return
      }

      if (!result.profile) {
        throw new Error('Seu perfil ainda não está ativo. Fale com o responsável pela sua conta.')
      }

      const redirectTo =
        (location.state as { from?: { pathname?: string } } | null)?.from?.pathname ??
        getRolePath(result.profile.role)
      navigate(redirectTo, { replace: true })
    } catch (caught) {
      setFeedback(caught instanceof Error ? caught.message : 'Não foi possível entrar.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card className="p-7" variant="glass">
      <div className="mb-7">
        <span className="inline-flex rounded-full border border-slate-200 bg-white/80 px-3 py-1 text-xs font-bold text-slate-600 shadow-sm dark:border-white/10 dark:bg-white/10 dark:text-slate-300">
          Acesso seguro
        </span>
        <h2 className="mt-4 text-3xl font-black tracking-tight">Entrar no Star Nutri</h2>
        <p className="mt-2 text-sm leading-6 text-slate-500 dark:text-slate-400">
          Acesse sua conta para acompanhar pacientes, planos e evolução nutricional.
        </p>
        {redirectedFrom && (
          <p className="mt-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm font-semibold text-amber-800 dark:border-amber-400/20 dark:bg-amber-400/10 dark:text-amber-300">
            Para acessar {redirectedFrom}, entre com uma conta autorizada.
          </p>
        )}
      </div>

      <form className="space-y-4" onSubmit={submit}>
        <FieldError error={errors.email} icon={<Mail size={17} />} label="E-mail">
          <Input
            autoComplete="email"
            onChange={(event) => setForm({ ...form, email: event.target.value })}
            placeholder="email@exemplo.com"
            type="text"
            value={form.email}
          />
        </FieldError>

        <FieldError error={errors.password} icon={<LockKeyhole size={17} />} label="Senha">
          <Input
            autoComplete="current-password"
            onChange={(event) => setForm({ ...form, password: event.target.value })}
            placeholder="Sua senha"
            type="password"
            value={form.password}
          />
        </FieldError>

        {feedback && (
          <p className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm font-semibold text-rose-700 dark:border-rose-400/20 dark:bg-rose-400/10 dark:text-rose-300">
            {feedback}
          </p>
        )}

        <Button className="w-full" disabled={loading} type="submit" variant="premium">
          {loading ? 'Validando acesso...' : 'Entrar'}
          <ArrowRight size={18} />
        </Button>
      </form>

      <div className="mt-6 space-y-3 text-sm">
        <Link className="font-semibold text-slate-500 transition hover:text-slate-950 dark:text-slate-400 dark:hover:text-white" to="/forgot-password">
          Esqueci a senha
        </Link>
        <p className="rounded-xl border border-slate-200/80 bg-slate-50/80 p-3 text-xs font-semibold leading-5 text-slate-500 dark:border-white/10 dark:bg-white/[0.04] dark:text-slate-400">
          Pacientes recebem o acesso diretamente pelo nutricionista responsável.
        </p>
      </div>
    </Card>
  )
}

export function FieldError({
  children,
  error,
  icon,
  label,
}: {
  children: React.ReactNode
  error?: string
  icon?: React.ReactNode
  label?: string
}) {
  return (
    <label className="block">
      {label && (
        <span className="mb-1.5 flex items-center gap-2 text-sm font-semibold text-slate-700 dark:text-slate-200">
          {icon}
          {label}
        </span>
      )}
      {children}
      {error && <span className="mt-1.5 block text-xs font-semibold text-rose-600">{error}</span>}
    </label>
  )
}
