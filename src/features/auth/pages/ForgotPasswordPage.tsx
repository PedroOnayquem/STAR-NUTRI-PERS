import { Link } from 'react-router-dom'
import { useState, type FormEvent } from 'react'
import { Button } from '../../../components/ui/Button'
import { Card } from '../../../components/ui/Card'
import { Input } from '../../../components/ui/Input'
import { useAuth } from '../useAuth'
import { validateEmail } from '../validation'
import { FieldError } from './LoginPage'

export function ForgotPasswordPage() {
  const { recoverPassword } = useAuth()
  const [email, setEmail] = useState('')
  const [error, setError] = useState<string | undefined>()
  const [feedback, setFeedback] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [loading, setLoading] = useState(false)

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const emailError = validateEmail(email)
    setError(emailError ?? undefined)
    setFeedback(null)

    if (emailError) {
      return
    }

    setLoading(true)
    try {
      await recoverPassword({ email })
      setFeedback({
        type: 'success',
        text: 'Enviamos as instrucoes de recuperacao para o email informado.',
      })
    } catch (caught) {
      setFeedback({
        type: 'error',
        text: caught instanceof Error ? caught.message : 'Nao foi possivel enviar o email.',
      })
    } finally {
      setLoading(false)
    }
  }

  return (
    <Card className="w-full max-w-md p-6">
      <h2 className="text-2xl font-black">Recuperar senha</h2>
      <p className="mt-2 text-sm text-slate-500 dark:text-slate-400">
        Informe o email da conta para receber o link de recuperacao.
      </p>

      <form className="mt-6 space-y-4" onSubmit={submit}>
        <FieldError error={error}>
          <Input
            autoComplete="email"
            onChange={(event) => setEmail(event.target.value)}
            placeholder="email@exemplo.com"
            type="email"
            value={email}
          />
        </FieldError>

        {feedback && (
          <p
            className={`rounded-lg border p-3 text-sm font-medium ${
              feedback.type === 'success'
                ? 'border-emerald-200 bg-emerald-50 text-emerald-700 dark:border-emerald-900 dark:bg-emerald-950 dark:text-emerald-300'
                : 'border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-900 dark:bg-rose-950 dark:text-rose-300'
            }`}
          >
            {feedback.text}
          </p>
        )}

        <Button className="w-full" disabled={loading} type="submit">
          {loading ? 'Enviando...' : 'Enviar link'}
        </Button>
      </form>

      <Link
        className="mt-5 block text-sm font-semibold text-emerald-700 dark:text-emerald-300"
        to="/login"
      >
        Voltar para login
      </Link>
    </Card>
  )
}
