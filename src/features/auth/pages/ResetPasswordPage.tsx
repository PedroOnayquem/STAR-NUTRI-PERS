import { CheckCircle2, KeyRound, ShieldCheck } from 'lucide-react'
import { useState, type FormEvent } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Button } from '../../../components/ui/Button'
import { Card } from '../../../components/ui/Card'
import { Input } from '../../../components/ui/Input'
import type { ChangePasswordInput } from '../types'
import { useAuth } from '../useAuth'
import {
  getStrongPasswordChecklist,
  validateChangePassword,
} from '../validation'
import { FieldError } from './LoginPage'

export function ResetPasswordPage() {
  const navigate = useNavigate()
  const {
    isPasswordRecovery,
    loading: authLoading,
    resetRecoveredPassword,
    session,
  } = useAuth()
  const [form, setForm] = useState<ChangePasswordInput>({
    password: '',
    confirmPassword: '',
  })
  const [errors, setErrors] = useState<
    Partial<Record<keyof ChangePasswordInput, string>>
  >({})
  const [feedback, setFeedback] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const checks = getStrongPasswordChecklist(form.password)
  const recoveryReady = isPasswordRecovery && Boolean(session)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const nextErrors = validateChangePassword(form)
    setErrors(nextErrors)
    setFeedback(null)

    if (Object.keys(nextErrors).length > 0) {
      return
    }

    if (!recoveryReady) {
      setFeedback(
        'Este link de recuperação é inválido ou expirou. Solicite um novo link.',
      )
      return
    }

    setSubmitting(true)
    try {
      await resetRecoveredPassword(form)
      navigate('/', { replace: true })
    } catch (caught) {
      setFeedback(
        caught instanceof Error
          ? caught.message
          : 'Não foi possível atualizar a senha.',
      )
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <Card className="p-7" variant="glass">
      <div className="mb-7">
        <span className="inline-flex items-center gap-2 rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-700 shadow-sm dark:border-emerald-400/20 dark:bg-emerald-400/10 dark:text-emerald-300">
          <ShieldCheck size={14} />
          Recuperação segura
        </span>
        <h2 className="mt-4 text-3xl font-black tracking-tight">
          Crie uma nova senha
        </h2>
        <p className="mt-2 text-sm leading-6 text-slate-500 dark:text-slate-400">
          Escolha uma senha forte para recuperar o acesso à sua conta.
        </p>
      </div>

      {!authLoading && !recoveryReady && (
        <p className="mb-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm font-semibold text-amber-800 dark:border-amber-400/20 dark:bg-amber-400/10 dark:text-amber-300">
          Este link não é mais válido. Solicite uma nova recuperação de senha.
        </p>
      )}

      <form className="space-y-4" onSubmit={submit}>
        <FieldError error={errors.password} icon={<KeyRound size={17} />} label="Nova senha">
          <Input
            autoComplete="new-password"
            disabled={!recoveryReady}
            onChange={(event) => setForm({ ...form, password: event.target.value })}
            placeholder="Nova senha"
            type="password"
            value={form.password}
          />
        </FieldError>

        <FieldError
          error={errors.confirmPassword}
          icon={<CheckCircle2 size={17} />}
          label="Confirmar nova senha"
        >
          <Input
            autoComplete="new-password"
            disabled={!recoveryReady}
            onChange={(event) =>
              setForm({ ...form, confirmPassword: event.target.value })
            }
            placeholder="Confirme a nova senha"
            type="password"
            value={form.confirmPassword}
          />
        </FieldError>

        <div className="rounded-2xl border border-slate-200/80 bg-slate-50/80 p-4 dark:border-white/10 dark:bg-white/[0.04]">
          <p className="text-xs font-black uppercase tracking-wide text-slate-500 dark:text-slate-400">
            Requisitos de segurança
          </p>
          <div className="mt-3 space-y-2">
            {checks.map((check) => (
              <div className="flex items-center gap-2 text-sm" key={check.label}>
                <CheckCircle2
                  className={
                    check.passed
                      ? 'text-emerald-600 dark:text-emerald-300'
                      : 'text-slate-300 dark:text-slate-600'
                  }
                  size={16}
                />
                <span
                  className={
                    check.passed
                      ? 'font-semibold text-emerald-700 dark:text-emerald-300'
                      : 'text-slate-500 dark:text-slate-400'
                  }
                >
                  {check.label}
                </span>
              </div>
            ))}
          </div>
        </div>

        {feedback && (
          <p className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm font-semibold text-rose-700 dark:border-rose-400/20 dark:bg-rose-400/10 dark:text-rose-300">
            {feedback}
          </p>
        )}

        <Button
          className="w-full"
          disabled={authLoading || submitting || !recoveryReady}
          type="submit"
          variant="premium"
        >
          {submitting ? 'Atualizando senha...' : 'Salvar nova senha'}
        </Button>
      </form>

      <Link
        className="mt-5 block text-sm font-semibold text-emerald-700 dark:text-emerald-300"
        to="/forgot-password"
      >
        Solicitar um novo link
      </Link>
    </Card>
  )
}
