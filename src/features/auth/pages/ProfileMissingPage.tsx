import { Link } from 'react-router-dom'
import { AlertTriangle } from 'lucide-react'
import { Button } from '../../../components/ui/Button'
import { Card } from '../../../components/ui/Card'
import { useAuth } from '../useAuth'

export function ProfileMissingPage() {
  const { logout, user } = useAuth()

  return (
    <main className="flex min-h-screen items-center justify-center bg-slate-50 px-6 text-slate-950 dark:bg-slate-950 dark:text-white">
      <Card className="max-w-lg p-6 text-center">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-lg bg-amber-50 text-amber-700 dark:bg-amber-950 dark:text-amber-300">
          <AlertTriangle size={24} />
        </div>
        <h1 className="mt-4 text-2xl font-black">Perfil não encontrado</h1>
        <p className="mt-3 text-sm leading-6 text-slate-600 dark:text-slate-300">
          Não encontramos um perfil ativo para {user?.email ?? 'este usuário'}.
          Solicite ao responsável pela sua conta a ativação do acesso.
        </p>
        <div className="mt-6 flex flex-col gap-2 sm:flex-row sm:justify-center">
          <Button onClick={logout} type="button">
            Sair
          </Button>
          <Button type="button" variant="secondary">
            <Link to="/login">Voltar ao login</Link>
          </Button>
        </div>
      </Card>
    </main>
  )
}
