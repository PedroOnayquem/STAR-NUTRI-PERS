import { Bot, Send, Sparkles } from 'lucide-react'
import { useMemo, useState } from 'react'
import type {
  ChatMessage,
  Diet,
  HealthCondition,
  Patient,
  PatientMetric,
  Workout,
} from '../../types'
import { buildPatientAiContext, generateGuardedAiReply } from '../../lib/aiContext'
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'
import { Textarea } from '../ui/Input'

type ChatBoxProps = {
  patient: Patient
  diet?: Diet
  workout?: Workout
  conditions: HealthCondition[]
  mainMetrics: PatientMetric[]
  variableMetrics: PatientMetric[]
  messages: ChatMessage[]
  onMessagesChange: (messages: ChatMessage[]) => void
}

export function ChatBox({
  patient,
  diet,
  workout,
  conditions,
  mainMetrics,
  variableMetrics,
  messages,
  onMessagesChange,
}: ChatBoxProps) {
  const [content, setContent] = useState('')
  const aiContext = useMemo(
    () =>
      buildPatientAiContext({
        patient,
        diet,
        workout,
        conditions,
        mainMetrics,
        variableMetrics,
        recentMessages: messages.slice(-8),
      }),
    [conditions, diet, mainMetrics, messages, patient, variableMetrics, workout],
  )

  function sendMessage() {
    if (!content.trim()) {
      return
    }

    const patientMessage: ChatMessage = {
      id: crypto.randomUUID(),
      sender: 'patient',
      content,
      createdAt: new Date().toISOString(),
    }

    const aiMessage: ChatMessage = {
      id: crypto.randomUUID(),
      sender: 'ai',
      content: generateGuardedAiReply(
        {
          patient,
          diet,
          workout,
          conditions,
          mainMetrics,
          variableMetrics,
          recentMessages: messages.slice(-8),
        },
        content,
      ),
      createdAt: new Date().toISOString(),
    }

    onMessagesChange([...messages, patientMessage, aiMessage])
    setContent('')
  }

  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_360px]">
      <Card className="flex min-h-[620px] flex-col overflow-hidden">
        <div className="border-b border-slate-200 p-4 dark:border-slate-800">
          <div className="flex items-center gap-3">
            <div className="rounded-lg bg-emerald-50 p-2 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
              <Bot size={20} />
            </div>
            <div>
              <h3 className="font-bold">Chat IA ChatGPT</h3>
              <p className="text-sm text-slate-500 dark:text-slate-400">
                Respostas limitadas ao plano cadastrado
              </p>
            </div>
          </div>
        </div>

        <div className="flex-1 space-y-4 overflow-y-auto p-4">
          {messages.map((message) => (
            <div
              className={`flex ${
                message.sender === 'patient' ? 'justify-end' : 'justify-start'
              }`}
              key={message.id}
            >
              <div
                className={`max-w-[78%] rounded-lg px-4 py-3 text-sm leading-6 ${
                  message.sender === 'patient'
                    ? 'bg-emerald-600 text-white'
                    : 'bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-100'
                }`}
              >
                {message.content}
              </div>
            </div>
          ))}
        </div>

        <div className="border-t border-slate-200 p-4 dark:border-slate-800">
          <div className="flex flex-col gap-3 sm:flex-row">
            <Textarea
              aria-label="Mensagem para IA"
              onChange={(event) => setContent(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault()
                  sendMessage()
                }
              }}
              placeholder="Ex.: Posso trocar o pre-treino por outra opcao?"
              value={content}
            />
            <Button className="sm:self-end" onClick={sendMessage} type="button">
              <Send size={18} />
              Enviar
            </Button>
          </div>
        </div>
      </Card>

      <Card className="p-5">
        <div className="flex items-center gap-2">
          <Sparkles className="text-emerald-600" size={18} />
          <h3 className="font-bold">Contexto enviado para IA</h3>
        </div>
        <div className="mt-4 space-y-4 text-sm">
          <ContextItem label="Modelo" value={aiContext.model} />
          <ContextItem label="Paciente" value={aiContext.patient.name} />
          <ContextItem label="Objetivo" value={aiContext.patient.objective} />
          <ContextItem label="Dieta" value={aiContext.diet} />
          <ContextItem label="Treino" value={aiContext.workout} />
          <ContextList label="Metricas" values={aiContext.mainMetrics} />
          <ContextList label="Condicoes" values={aiContext.conditions} />
        </div>
      </Card>
    </div>
  )
}

function ContextItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">
        {label}
      </p>
      <p className="mt-1 leading-6">{value}</p>
    </div>
  )
}

function ContextList({ label, values }: { label: string; values: string[] }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">
        {label}
      </p>
      <div className="mt-2 space-y-2">
        {values.length ? (
          values.map((value) => (
            <p className="rounded-lg bg-slate-50 p-2 dark:bg-slate-950" key={value}>
              {value}
            </p>
          ))
        ) : (
          <p className="text-slate-500 dark:text-slate-400">Nao informado</p>
        )}
      </div>
    </div>
  )
}
