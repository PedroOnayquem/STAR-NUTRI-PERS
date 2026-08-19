import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Activity, Bot, Clock3, FileCheck2, FileWarning, Files } from 'lucide-react'
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { Badge } from '../components/ui/Badge'
import { Card } from '../components/ui/Card'
import { EmptyState } from '../components/ui/EmptyState'
import { SectionHeader } from '../components/ui/SectionHeader'
import { PageSkeleton } from '../components/ui/Skeleton'
import { StatCard } from '../components/ui/StatCard'
import { useAuth } from '../features/auth/useAuth'
import { getFileMonitoring } from '../features/files/fileMonitoringService'

export function FileMonitoringPage() {
  const { session, profile } = useAuth()
  const [days, setDays] = useState(30)
  const query = useQuery({
    queryKey: ['file-monitoring', days],
    queryFn: () => getFileMonitoring(session, days),
    enabled: Boolean(session),
  })
  if (query.isLoading) return <PageSkeleton />
  if (query.error) throw query.error
  const data = query.data!

  return (
    <div className="space-y-6">
      <SectionHeader
        eyebrow={<Badge tone="blue">Dados reais</Badge>}
        title="Monitoramento de arquivos"
        description={profile?.role === 'admin'
          ? 'Visão operacional de todos os arquivos processados pelo Star Nutri.'
          : 'Acompanhe arquivos enviados para seus pacientes, processamento e utilização pela IA.'}
      />
      <div className="flex gap-2">
        {[7, 30, 90].map((value) => (
          <button key={value} type="button" onClick={() => setDays(value)}
            className={`rounded-xl px-4 py-2 text-sm font-bold ${days === value ? 'bg-slate-950 text-white dark:bg-white dark:text-slate-950' : 'border border-slate-200 bg-white text-slate-600 dark:border-white/10 dark:bg-white/[0.04] dark:text-slate-300'}`}>
            {value} dias
          </button>
        ))}
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
        <StatCard icon={<Files size={20} />} label="Arquivos" value={data.summary.files} caption={`${data.summary.imports} importações`} />
        <StatCard icon={<FileCheck2 size={20} />} label="Concluídos" value={data.summary.processed} caption="processados ou vinculados" />
        <StatCard icon={<FileWarning size={20} />} label="Falhas" value={data.summary.failed} caption="erros reais no período" />
        <StatCard icon={<Clock3 size={20} />} label="Tempo médio" value={formatDuration(data.summary.average_processing_ms)} caption={`${data.summary.measured_processing_count} com tempo medido`} />
        <StatCard icon={<Bot size={20} />} label="Uso pela IA" value={data.summary.ai_usage_count} caption={`${data.summary.file_access_count} acessos aos arquivos`} />
      </div>

      <div className="grid gap-4 xl:grid-cols-[2fr_1fr]">
        <Card className="p-5">
          <h2 className="font-black">Evolução no período</h2>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">Uploads, falhas e consultas pela IA por dia.</p>
          <div className="mt-5 h-72">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data.daily}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.2} />
                <XAxis dataKey="date" tickFormatter={(value) => value.slice(5)} fontSize={12} />
                <YAxis allowDecimals={false} fontSize={12} />
                <Tooltip />
                <Line dataKey="files" name="Arquivos" stroke="#10b981" strokeWidth={3} />
                <Line dataKey="failed" name="Falhas" stroke="#f43f5e" strokeWidth={2} />
                <Line dataKey="ai_uses" name="Uso IA" stroke="#0ea5e9" strokeWidth={2} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </Card>
        <Card className="p-5">
          <h2 className="font-black">Erros recorrentes</h2>
          <div className="mt-4 space-y-3">
            {data.recurring_errors.length ? data.recurring_errors.map((error) => (
              <div key={`${error.code}-${error.message}`} className="rounded-xl border border-rose-200 bg-rose-50 p-3 dark:border-rose-400/20 dark:bg-rose-400/10">
                <div className="flex justify-between gap-3"><strong className="text-sm text-rose-800 dark:text-rose-200">{error.code}</strong><Badge tone="amber">{error.count}x</Badge></div>
                <p className="mt-1 line-clamp-2 text-xs text-rose-700 dark:text-rose-300">{error.message}</p>
              </div>
            )) : <p className="text-sm text-slate-500">Nenhuma falha registrada no período.</p>}
          </div>
        </Card>
      </div>

      <Card className="overflow-hidden p-0">
        <div className="border-b border-slate-200 p-5 dark:border-white/10"><h2 className="font-black">Arquivos recentes</h2></div>
        {!data.imports.length ? <div className="p-5"><EmptyState title="Nenhum arquivo no período" description="Os próximos uploads aparecerão aqui com métricas reais." /></div> : (
          <div className="divide-y divide-slate-100 dark:divide-white/10">
            {data.imports.map((item) => (
              <div key={item.id} className="grid gap-3 p-5 lg:grid-cols-[2fr_1fr_1fr_1fr_auto] lg:items-center">
                <div><p className="font-bold">{item.files.map((file) => file.original_file_name).filter(Boolean).join(', ') || item.original_file_name || 'Arquivo sem nome'}</p><p className="mt-1 text-xs text-slate-500">{item.patient?.name || 'Ainda não vinculado'} · {new Date(item.created_at).toLocaleString('pt-BR')}</p></div>
                <div className="text-sm"><p className="font-semibold">{item.file_type?.toUpperCase() || 'N/D'}</p><p className="text-xs text-slate-500">{formatBytes(item.file_size_bytes)}</p></div>
                <div className="text-sm"><p className="font-semibold">{formatDuration(item.processing_duration_ms)}</p><p className="text-xs text-slate-500">processamento</p></div>
                <div className="text-sm"><p className="flex items-center gap-1 font-semibold"><Bot size={14} /> {item.ai_usage_count}</p><p className="text-xs text-slate-500">usos no contexto</p></div>
                <StatusBadge status={item.status} />
                {item.error_message && <p className="lg:col-span-5 rounded-xl bg-rose-50 p-3 text-xs text-rose-700 dark:bg-rose-400/10 dark:text-rose-300">{item.error_code}: {item.error_message}</p>}
              </div>
            ))}
          </div>
        )}
      </Card>
      <p className="flex items-center gap-2 text-xs text-slate-500"><Activity size={14} /> Uso pela IA indica que dados derivados do lote entraram no contexto do modelo; não significa que o arquivo foi citado na resposta.</p>
    </div>
  )
}

function StatusBadge({ status }: { status: string }) {
  const label = ({ linked: 'Vinculado', processed: 'Processado', failed: 'Falhou', processing: 'Processando', pending: 'Pendente' } as Record<string, string>)[status] || status
  return <Badge tone={status === 'failed' ? 'amber' : status === 'linked' || status === 'processed' ? 'green' : 'blue'}>{label}</Badge>
}
function formatDuration(value: number | null) { return value == null ? 'Não medido' : value < 1000 ? `${value} ms` : `${(value / 1000).toFixed(1)} s` }
function formatBytes(value: number | null) { if (value == null) return 'Tamanho não informado'; if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`; return `${(value / 1024 / 1024).toFixed(1)} MB` }
