import { Component, type ErrorInfo, type ReactNode } from 'react'
import { AlertTriangle } from 'lucide-react'
import { friendlyErrorMessage, USER_MESSAGES } from '../constants/messages'
import { Button } from './ui/Button'
import { Card } from './ui/Card'

type State = {
  error: Error | null
}

export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { error: null }

  static getDerivedStateFromError(error: Error) {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Star Nutri boundary error', error, info)
  }

  render() {
    if (!this.state.error) {
      return this.props.children
    }

    return (
      <main className="flex min-h-screen items-center justify-center bg-slate-50 p-4 text-slate-950 dark:bg-slate-950 dark:text-white">
        <Card className="max-w-lg p-6 text-center">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-rose-500/10 text-rose-600 dark:text-rose-300">
            <AlertTriangle size={22} />
          </div>
          <h1 className="mt-4 text-xl font-black">Não foi possível carregar esta área</h1>
          <p className="mt-2 text-sm leading-6 text-slate-500 dark:text-slate-400">
            {friendlyErrorMessage(this.state.error, USER_MESSAGES.actionError)}
          </p>
          <Button className="mt-5" onClick={() => window.location.reload()} variant="premium">
            Recarregar
          </Button>
        </Card>
      </main>
    )
  }
}
