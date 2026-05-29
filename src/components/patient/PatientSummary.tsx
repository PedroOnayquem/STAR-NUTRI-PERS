import { AlertTriangle, CalendarDays, Mail, Target } from 'lucide-react'
import type {
  Diet,
  HealthCondition,
  Patient,
  PatientMetric,
  Workout,
} from '../../types'
import { Badge } from '../ui/Badge'
import { Card } from '../ui/Card'

type PatientSummaryProps = {
  patient: Patient
  diet?: Diet
  workout?: Workout
  mainMetrics: PatientMetric[]
  variableMetrics: PatientMetric[]
  conditions: HealthCondition[]
}

export function PatientSummary({
  patient,
  diet,
  workout,
  mainMetrics,
  variableMetrics,
  conditions,
}: PatientSummaryProps) {
  return (
    <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
      <Card className="p-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h2 className="text-2xl font-bold">{patient.fullName}</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600 dark:text-slate-300">
              {patient.notes}
            </p>
          </div>
          <Badge tone={patient.isActive ? 'green' : 'red'}>
            {patient.isActive ? 'Ativo' : 'Inativo'}
          </Badge>
        </div>

        <div className="mt-5 grid gap-3 sm:grid-cols-3">
          <Info icon={<Mail size={16} />} label="E-mail" value={patient.email} />
          <Info icon={<CalendarDays size={16} />} label="Nascimento" value={patient.birthDate} />
          <Info icon={<Target size={16} />} label="Objetivo" value={patient.objective} />
        </div>
      </Card>

      <Card className="p-5">
        <div className="flex items-center gap-2">
          <AlertTriangle className="text-amber-600" size={18} />
          <h3 className="font-bold">Alertas clínicos</h3>
        </div>
        <div className="mt-4 space-y-3">
          <Alert label="Dieta ativa" ok={Boolean(diet)} />
          <Alert label="Treino ativo" ok={Boolean(workout)} />
          <Alert
            label="Métricas recentes"
            ok={variableMetrics.length > 0}
          />
          <Alert
            label="Individualidades registradas"
            ok={conditions.length > 0}
          />
        </div>
      </Card>

      <Card className="p-5 xl:col-span-2">
        <h3 className="font-bold">Métricas principais</h3>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {mainMetrics.map((metric) => (
            <div
              className="rounded-lg border border-slate-200 bg-slate-50 p-4 dark:border-slate-800 dark:bg-slate-950"
              key={metric.id}
            >
              <p className="text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">
                {metric.name}
              </p>
              <p className="mt-2 text-xl font-bold">
                {metric.value} {metric.unit}
              </p>
            </div>
          ))}
        </div>
      </Card>
    </div>
  )
}

function Info({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode
  label: string
  value: string
}) {
  return (
    <div className="rounded-lg bg-slate-50 p-3 dark:bg-slate-950">
      <div className="flex items-center gap-2 text-slate-500 dark:text-slate-400">
        {icon}
        <span className="text-xs font-semibold uppercase">{label}</span>
      </div>
      <p className="mt-2 text-sm font-semibold">{value}</p>
    </div>
  )
}

function Alert({ label, ok }: { label: string; ok: boolean }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-lg bg-slate-50 px-3 py-2 dark:bg-slate-950">
      <span className="text-sm font-medium">{label}</span>
      <Badge tone={ok ? 'green' : 'amber'}>{ok ? 'OK' : 'Pendente'}</Badge>
    </div>
  )
}
