import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm, useWatch } from 'react-hook-form'
import { z } from 'zod'
import { Link, useNavigate } from 'react-router-dom'
import { AlertTriangle, CheckCircle2, FileText, Mail, Plus, Search, Upload, UserCheck, UserPlus, Users, X } from 'lucide-react'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { EmptyState } from '../../components/ui/EmptyState'
import { AppDatePicker } from '../../components/ui/FormControls'
import { Input, Textarea } from '../../components/ui/Input'
import { SectionHeader } from '../../components/ui/SectionHeader'
import { PageSkeleton } from '../../components/ui/Skeleton'
import { useAuth } from '../../features/auth/useAuth'
import {
  activateNutritionistPatient,
  getNutritionistWorkspace,
} from '../../features/clinical/services/workspaceService'
import {
  createPatient,
  importBioimpedanceReport,
  type BioimpedanceImportResult,
  type CreatePatientInput,
} from '../../features/nutritionist/services/patientService'
import { useDeferredValue, useMemo, useRef, useState } from 'react'

const BIOIMPEDANCE_REPORT_ACCEPT = '.pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png'
const MAX_BIOIMPEDANCE_REPORT_BYTES = 10 * 1024 * 1024
const MAX_BIOIMPEDANCE_REPORT_FILES = 5
const MAX_BIOIMPEDANCE_REPORT_TOTAL_BYTES = 25 * 1024 * 1024
const ALLOWED_REPORT_EXTENSIONS = new Set(['pdf', 'jpg', 'jpeg', 'png'])
const ALLOWED_REPORT_MIME_TYPES = new Set(['application/pdf', 'image/jpeg', 'image/png'])

type SelectedImportFile = {
  id: string
  file: File
  error: string | null
}
type PatientStatusFilter = 'ALL' | 'TRIAL' | 'ACTIVE' | 'EXPIRED'

const patientSchema = z.object({
  fullName: z.string().min(3, 'Informe o nome completo.'),
  email: z.string().email('Informe um e-mail válido.'),
  password: z.string().min(6, 'A senha deve ter pelo menos 6 caracteres.'),
  birthDate: z.string(),
  gender: z.string(),
  objective: z.string(),
  notes: z.string().max(1000, 'Máximo de 1000 caracteres.'),
})

function validateBioimpedanceReportFile(file: File) {
  if (file.size > MAX_BIOIMPEDANCE_REPORT_BYTES) {
    return `O arquivo "${file.name}" deve ter no máximo 10 MB.`
  }

  const extension = file.name.split('.').pop()?.toLowerCase()
  if (!extension || !ALLOWED_REPORT_EXTENSIONS.has(extension)) {
    return `O arquivo "${file.name}" não é compatível. Envie apenas PDF, JPG, JPEG ou PNG.`
  }

  const mimeType = file.type.toLowerCase()
  if (mimeType && !ALLOWED_REPORT_MIME_TYPES.has(mimeType)) {
    return `O arquivo "${file.name}" não é compatível. Envie apenas PDF, JPG, JPEG ou PNG.`
  }

  return null
}

function validateBioimpedanceReportBatch(files: SelectedImportFile[]) {
  if (files.length > MAX_BIOIMPEDANCE_REPORT_FILES) {
    return `Envie no máximo ${MAX_BIOIMPEDANCE_REPORT_FILES} arquivos por importação.`
  }

  const totalSize = files.reduce((sum, item) => sum + item.file.size, 0)
  if (totalSize > MAX_BIOIMPEDANCE_REPORT_TOTAL_BYTES) {
    return 'A importação completa deve ter no máximo 25 MB.'
  }

  return null
}

function fileTypeLabel(file: File) {
  const extension = file.name.split('.').pop()?.toUpperCase()
  return extension || file.type || 'Arquivo'
}

function formatFileSize(bytes: number) {
  if (bytes >= 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1).replace('.', ',')} MB`
  return `${Math.max(1, Math.round(bytes / 1024))} KB`
}

export function PatientsPage({ mode = 'list' }: { mode?: 'list' | 'create' }) {
  const { session } = useAuth()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState<PatientStatusFilter>('ALL')
  const deferredSearch = useDeferredValue(search)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [reportImport, setReportImport] = useState<BioimpedanceImportResult | null>(null)
  const [fileValidationError, setFileValidationError] = useState<string | null>(null)
  const [selectedImportFiles, setSelectedImportFiles] = useState<SelectedImportFile[]>([])
  const [autofilledFields, setAutofilledFields] = useState<Set<string>>(new Set())

  const workspaceQuery = useQuery({
    queryKey: ['nutritionist-workspace'],
    queryFn: () => getNutritionistWorkspace(session),
    enabled: Boolean(session),
  })

  const form = useForm<CreatePatientInput>({
    resolver: zodResolver(patientSchema),
    defaultValues: {
      fullName: '',
      email: '',
      password: '',
      birthDate: '',
      gender: '',
      objective: '',
      notes: '',
    },
  })
  const birthDate = useWatch({ control: form.control, name: 'birthDate' })

  const createMutation = useMutation({
    mutationFn: (payload: CreatePatientInput) => createPatient(payload, session),
    onSuccess: (created) => {
      queryClient.invalidateQueries({ queryKey: ['nutritionist-workspace'] })
      navigate(`/nutritionist/patients/${created.patient_id}`)
    },
  })
  const activateMutation = useMutation({
    mutationFn: (patientId: string) => activateNutritionistPatient(patientId, session),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['nutritionist-workspace'] })
      queryClient.invalidateQueries({ queryKey: ['nutritionist-dashboard'] })
    },
  })

  const importMutation = useMutation({
    mutationFn: (files: File[]) => importBioimpedanceReport(files, session),
    onMutate: () => {
      setFileValidationError(null)
      setReportImport(null)
    },
    onSuccess: (result) => {
      setReportImport(result)
      const filled = new Set<string>()
      if (result.patient.full_name) {
        form.setValue('fullName', result.patient.full_name, { shouldDirty: true, shouldValidate: true })
        filled.add('fullName')
      }
      if (result.patient.gender) {
        form.setValue('gender', result.patient.gender, { shouldDirty: true, shouldValidate: true })
        filled.add('gender')
      }
      if (result.patient.birth_date) {
        form.setValue('birthDate', result.patient.birth_date, { shouldDirty: true, shouldValidate: true })
        filled.add('birthDate')
      }
      if (result.patient.notes) {
        form.setValue('notes', result.patient.notes, { shouldDirty: true, shouldValidate: true })
        filled.add('notes')
      }
      setAutofilledFields(filled)
    },
  })

  const validImportFiles = selectedImportFiles.filter((item) => !item.error)
  const batchValidationError = validateBioimpedanceReportBatch(selectedImportFiles)

  function addImportFiles(files: FileList | null) {
    if (!files?.length) return

    const nextFiles = [
      ...selectedImportFiles,
      ...Array.from(files).map((file) => ({
        id: `${file.name}-${file.size}-${file.lastModified}-${crypto.randomUUID()}`,
        file,
        error: validateBioimpedanceReportFile(file),
      })),
    ]
    setSelectedImportFiles(nextFiles)
    setReportImport(null)
    setFileValidationError(validateBioimpedanceReportBatch(nextFiles))
  }

  function removeImportFile(id: string) {
    const nextFiles = selectedImportFiles.filter((item) => item.id !== id)
    setSelectedImportFiles(nextFiles)
    setFileValidationError(validateBioimpedanceReportBatch(nextFiles))
  }

  function processSelectedImportFiles() {
    const invalidFile = selectedImportFiles.find((item) => item.error)
    if (invalidFile?.error) {
      setFileValidationError(invalidFile.error)
      return
    }
    const validationError = validateBioimpedanceReportBatch(selectedImportFiles)
    if (validationError) {
      setFileValidationError(validationError)
      return
    }
    if (validImportFiles.length === 0) {
      setFileValidationError('Selecione ao menos um arquivo válido para processar.')
      return
    }
    importMutation.mutate(validImportFiles.map((item) => item.file))
  }

  const patientStatusCounts = useMemo(() => {
    const all = workspaceQuery.data?.patients ?? []
    return {
      ACTIVE: all.filter((patient) => patient.access_status === 'ACTIVE').length,
      ALL: all.length,
      EXPIRED: all.filter((patient) => patient.access_status === 'EXPIRED').length,
      TRIAL: all.filter((patient) => patient.access_status === 'TRIAL').length,
    }
  }, [workspaceQuery.data?.patients])

  const patients = useMemo(() => {
    const all = workspaceQuery.data?.patients ?? []
    const term = deferredSearch.trim().toLowerCase()
    const filteredByStatus = statusFilter === 'ALL'
      ? all
      : all.filter((patient) => patient.access_status === statusFilter)
    if (!term) return filteredByStatus

    return filteredByStatus.filter((patient) => {
      const name = patient.profile?.full_name?.toLowerCase() ?? ''
      const email = patient.profile?.email?.toLowerCase() ?? ''
      const objective = patient.objective?.toLowerCase() ?? ''
      return name.includes(term) || email.includes(term) || objective.includes(term)
    })
  }, [deferredSearch, statusFilter, workspaceQuery.data?.patients])

  if (workspaceQuery.isLoading) return <PageSkeleton />
  if (workspaceQuery.error) throw workspaceQuery.error

  if (mode === 'create') {
    return (
      <div className="space-y-6">
        <SectionHeader
          description="Crie a conta do paciente e revise os dados antes de liberar o acesso."
          eyebrow={<Badge tone="green">Novo paciente</Badge>}
          title="Cadastrar paciente"
        />

        <Card className="p-6" variant="glass">
          <div className="mb-6 rounded-2xl border border-cyan-300/15 bg-cyan-400/5 p-4">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
              <div className="flex gap-3">
                <div className="grid h-11 w-11 shrink-0 place-items-center rounded-2xl bg-cyan-400/10 text-cyan-300">
                  <FileText size={22} />
                </div>
                <div>
                  <h2 className="font-black">Importar relatório de bioimpedância</h2>
                  <p className="mt-1 text-sm leading-6 text-slate-500 dark:text-slate-400">
                    Envie um ou mais arquivos do relatório gerado pela balança. Você pode enviar PDF, JPG, JPEG ou PNG,
                    incluindo frente e verso do relatório.
                  </p>
                  <p className="mt-1 text-xs font-bold uppercase text-cyan-700 dark:text-cyan-200">
                    Até {MAX_BIOIMPEDANCE_REPORT_FILES} arquivos. Máximo de 10 MB por arquivo e 25 MB no total.
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <input
                  accept={BIOIMPEDANCE_REPORT_ACCEPT}
                  className="hidden"
                  multiple
                  onChange={(event) => {
                    addImportFiles(event.target.files)
                    event.currentTarget.value = ''
                  }}
                  ref={fileInputRef}
                  type="file"
                />
                <Button
                  disabled={importMutation.isPending}
                  onClick={() => fileInputRef.current?.click()}
                  type="button"
                  variant="secondary"
                >
                  <Upload size={18} />
                  Selecionar arquivos
                </Button>
                <Button
                  disabled={
                    importMutation.isPending ||
                    validImportFiles.length === 0 ||
                    selectedImportFiles.some((item) => item.error) ||
                    Boolean(batchValidationError)
                  }
                  onClick={processSelectedImportFiles}
                  type="button"
                  variant="premium"
                >
                  <FileText size={18} />
                  {importMutation.isPending ? 'Processando...' : 'Processar arquivos'}
                </Button>
              </div>
            </div>

            {selectedImportFiles.length > 0 && (
              <div className="mt-4 rounded-2xl border border-white/10 bg-white/[0.03] p-3">
                <p className="text-sm font-black">Arquivos selecionados</p>
                <div className="mt-3 grid gap-2">
                  {selectedImportFiles.map((item, index) => (
                    <div
                      className="flex flex-col gap-2 rounded-xl border border-white/10 bg-slate-950/20 px-3 py-2 text-sm sm:flex-row sm:items-center sm:justify-between"
                      key={item.id}
                    >
                      <div>
                        <p className="font-bold">
                          {index + 1}. {item.file.name}
                        </p>
                        <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">
                          {fileTypeLabel(item.file)} · {formatFileSize(item.file.size)}
                        </p>
                        {item.error && (
                          <p className="mt-1 text-xs font-semibold text-rose-300">{item.error}</p>
                        )}
                      </div>
                      <button
                        className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-white/10 text-slate-400 hover:text-rose-200"
                        onClick={() => removeImportFile(item.id)}
                        type="button"
                        title="Remover arquivo"
                      >
                        <X size={15} />
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {(fileValidationError || importMutation.error) && (
              <p className="mt-4 rounded-xl border border-rose-400/20 bg-rose-400/10 px-4 py-3 text-sm font-semibold text-rose-200">
                {fileValidationError || importMutation.error?.message}
              </p>
            )}

            {reportImport && (
              <ImportReview result={reportImport} />
            )}
          </div>

          <form
            className="grid gap-4 md:grid-cols-2"
            onSubmit={form.handleSubmit((values) =>
              createMutation.mutate({ ...values, importId: reportImport?.import_id ?? null }),
            )}
          >
            <Field
              error={form.formState.errors.fullName?.message}
              label="Nome completo"
              source={autofilledFields.has('fullName')}
            >
              <Input placeholder="Lucas Andrade" {...form.register('fullName')} />
            </Field>
            <Field error={form.formState.errors.email?.message} label="E-mail">
              <Input placeholder="paciente@email.com" type="email" {...form.register('email')} />
            </Field>
            <Field error={form.formState.errors.password?.message} label="Senha provisória">
              <Input type="password" {...form.register('password')} />
            </Field>
            <Field
              error={form.formState.errors.birthDate?.message}
              label="Data de nascimento"
              source={autofilledFields.has('birthDate')}
            >
              <AppDatePicker
                error={form.formState.errors.birthDate?.message}
                value={birthDate}
                onChange={(value) => form.setValue('birthDate', value, { shouldDirty: true, shouldValidate: true })}
              />
            </Field>
            <Field
              error={form.formState.errors.gender?.message}
              label="Gênero"
              source={autofilledFields.has('gender')}
            >
              <Input placeholder="Feminino, masculino..." {...form.register('gender')} />
            </Field>
            <Field error={form.formState.errors.objective?.message} label="Objetivo">
              <Input placeholder="Emagrecimento, hipertrofia..." {...form.register('objective')} />
            </Field>
            <div className="md:col-span-2">
              <Field
                error={form.formState.errors.notes?.message}
                label="Histórico e observações"
                source={autofilledFields.has('notes')}
              >
                <Textarea
                  placeholder="Rotina, restrições, preferências, histórico clínico inicial..."
                  {...form.register('notes')}
                />
              </Field>
            </div>

            {createMutation.error && (
              <p className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-sm font-semibold text-rose-700 dark:border-rose-400/20 dark:bg-rose-400/10 dark:text-rose-300 md:col-span-2">
                {createMutation.error.message}
              </p>
            )}

            <div className="flex gap-2 md:col-span-2">
              <Button disabled={createMutation.isPending} type="submit" variant="premium">
                <UserPlus size={18} />
                {createMutation.isPending ? 'Cadastrando...' : 'Cadastrar paciente'}
              </Button>
              <Button asChild type="button" variant="secondary">
                <Link to="/nutritionist/patients">Cancelar</Link>
              </Button>
            </div>
          </form>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <SectionHeader
        actions={
          <Button asChild variant="premium">
            <Link to="/nutritionist/patients/new">
              <Plus size={18} />
              Novo paciente
            </Link>
          </Button>
        }
        description="Busque, abra detalhes, edite dados clínicos e gerencie planos reais."
        eyebrow={<Badge tone="blue">Gestão de pacientes</Badge>}
        title="Pacientes"
      />

      <Card className="p-4">
        <div className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white px-3 py-2 dark:border-white/10 dark:bg-white/[0.04]">
          <Search size={18} className="text-slate-400" />
          <input
            className="w-full bg-transparent text-sm outline-none placeholder:text-slate-400"
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Buscar por nome, e-mail ou objetivo"
            value={search}
          />
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {(['ALL', 'TRIAL', 'ACTIVE', 'EXPIRED'] as const).map((status) => (
            <button
              className={`inline-flex items-center gap-2 rounded-xl border px-3 py-2 text-sm font-bold transition ${
                statusFilter === status
                  ? 'border-cyan-300/40 bg-cyan-300/10 text-cyan-700 dark:text-cyan-200'
                  : 'border-slate-200 text-slate-600 hover:bg-slate-50 dark:border-white/10 dark:text-slate-300 dark:hover:bg-white/5'
              }`}
              key={status}
              onClick={() => setStatusFilter(status)}
              type="button"
            >
              {patientStatusFilterLabel(status)}
              <span className="rounded-full bg-slate-950 px-2 py-0.5 text-xs text-white dark:bg-white dark:text-slate-950">
                {patientStatusCounts[status]}
              </span>
            </button>
          ))}
        </div>
      </Card>

      {patients.length === 0 ? (
        <EmptyState
          action={
            <Button asChild variant="premium">
              <Link to="/nutritionist/patients/new">Cadastrar paciente</Link>
            </Button>
          }
          description="Cadastre um paciente para começar o acompanhamento."
          icon={<Users size={24} />}
          title="Nenhum paciente encontrado"
        />
      ) : (
        <div className="grid gap-4 lg:grid-cols-2">
          {patients.map((patient) => (
            <Link key={patient.id} to={`/nutritionist/patients/${patient.id}`}>
              <Card className="h-full p-5 transition hover:-translate-y-0.5 hover:shadow-xl">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <h2 className="text-lg font-black">{patient.profile?.full_name ?? 'Paciente'}</h2>
                    <p className="mt-1 flex items-center gap-2 text-sm text-slate-500 dark:text-slate-400">
                      <Mail size={15} />
                      {patient.profile?.email}
                    </p>
                  </div>
                  <Badge tone={patientStatusTone(patient.access_status)}>
                    {patientStatusLabel(patient)}
                  </Badge>
                </div>
                <p className="mt-4 text-sm leading-6 text-slate-600 dark:text-slate-300">
                  {patient.objective || 'Objetivo ainda não informado.'}
                </p>
                {patient.access_status === 'EXPIRED' && (
                  <Button
                    className="mt-4"
                    disabled={activateMutation.isPending}
                    onClick={(event) => {
                      event.preventDefault()
                      activateMutation.mutate(patient.id)
                    }}
                    size="sm"
                    type="button"
                    variant="premium"
                  >
                    <UserCheck size={16} />
                    Ativar paciente
                  </Button>
                )}
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}

function patientStatusFilterLabel(status: PatientStatusFilter) {
  const labels: Record<PatientStatusFilter, string> = {
    ACTIVE: 'Ativos',
    ALL: 'Todos',
    EXPIRED: 'Expirados',
    TRIAL: 'Em Trial',
  }
  return labels[status]
}

function patientStatusLabel(patient: { access_status: 'TRIAL' | 'ACTIVE' | 'EXPIRED'; trial_days_remaining?: number }) {
  if (patient.access_status === 'TRIAL') {
    return `Trial: ${patient.trial_days_remaining ?? 0} dias`
  }
  if (patient.access_status === 'ACTIVE') return 'Ativo'
  return 'Expirado'
}

function patientStatusTone(status: 'TRIAL' | 'ACTIVE' | 'EXPIRED') {
  if (status === 'TRIAL') return 'blue'
  if (status === 'ACTIVE') return 'green'
  return 'red'
}

function Field({
  children,
  error,
  label,
  source = false,
}: {
  children: React.ReactNode
  error?: string
  label: string
  source?: boolean
}) {
  return (
    <label className="block">
      <span className="mb-1.5 flex flex-wrap items-center gap-2 text-sm font-semibold text-slate-700 dark:text-slate-200">
        <span>{label}</span>
        {source && (
          <span className="rounded-full border border-emerald-300/20 bg-emerald-400/10 px-2 py-0.5 text-[11px] font-black uppercase text-emerald-300">
            Preenchido pelo relatório
          </span>
        )}
      </span>
      {children}
      {error && <span className="mt-1.5 block text-xs font-semibold text-rose-600">{error}</span>}
    </label>
  )
}

function ImportReview({ result }: { result: BioimpedanceImportResult }) {
  const patientRows = [
    { label: 'Nome', value: result.patient.full_name },
    { label: 'Gênero', value: result.patient.gender },
    {
      label: 'Data de nascimento',
      value: result.patient.birth_date ? formatDate(result.patient.birth_date) : undefined,
    },
    { label: 'Idade', value: result.patient.age ? `${result.patient.age} anos` : undefined },
    { label: 'Altura', value: result.patient.height_cm ? `${result.patient.height_cm} cm` : undefined },
  ].filter((item): item is { label: string; value: string } => Boolean(item.value))
  const metricRows = Object.entries(result.metrics)
    .map(([key, value]) => ({
      key,
      label: metricLabel(key),
      value: formatMetricValue(key, value),
      confidence: result.confidence[key],
    }))
    .filter((item) => item.value)

  return (
    <div className="mt-5 grid gap-4 xl:grid-cols-[0.9fr_1.1fr]">
      <div className="rounded-2xl border border-white/10 bg-slate-950/20 p-4">
        <div className="flex items-start gap-2">
          <CheckCircle2 className="mt-0.5 text-emerald-300" size={18} />
          <div>
            <h3 className="font-black">Dados encontrados no relatório</h3>
            <p className="mt-1 text-sm leading-6 text-slate-400">
              Revise os dados antes de cadastrar. Campos não encontrados permaneceram vazios.
            </p>
            <p className="mt-1 text-xs font-black uppercase text-emerald-200">
              Importação processada com {result.file_count} {result.file_count === 1 ? 'arquivo' : 'arquivos'}.
            </p>
          </div>
        </div>
        <div className="mt-4 grid gap-2">
          {patientRows.length === 0 ? (
            <p className="text-sm text-slate-400">Nenhum dado cadastral claro foi encontrado.</p>
          ) : (
            patientRows.map((item) => (
              <ReviewLine key={item.label} label={item.label} value={item.value} />
            ))
          )}
        </div>
      </div>

      <div className="rounded-2xl border border-white/10 bg-slate-950/20 p-4">
        <h3 className="font-black">Métricas preparadas</h3>
        <div className="premium-scrollbar mt-4 max-h-64 overflow-y-auto pr-1">
          {metricRows.length === 0 ? (
            <p className="text-sm text-slate-400">Nenhuma métrica corporal válida foi encontrada.</p>
          ) : (
            <div className="grid gap-2 sm:grid-cols-2">
              {metricRows.map((metric) => (
                <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3" key={metric.key}>
                  <p className="text-xs font-black uppercase text-slate-400">{metric.label}</p>
                  <div className="mt-1 flex flex-wrap items-center gap-2">
                    <p className="font-black">{metric.value}</p>
                    {typeof metric.confidence === 'number' && metric.confidence < 0.72 && (
                      <span className="rounded-full border border-amber-300/20 bg-amber-400/10 px-2 py-0.5 text-[11px] font-black uppercase text-amber-200">
                        Revisar
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {result.warnings.length > 0 && (
        <div className="rounded-2xl border border-amber-300/20 bg-amber-400/10 p-4 text-sm text-amber-100 xl:col-span-2">
          <div className="flex items-center gap-2 font-black">
            <AlertTriangle size={17} />
            Pontos para revisar
          </div>
          <ul className="mt-2 space-y-1">
            {result.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

function ReviewLine({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-xl bg-white/[0.03] px-3 py-2 text-sm">
      <span className="text-slate-400">{label}</span>
      <span className="text-right font-bold text-slate-100">{value}</span>
    </div>
  )
}

function metricLabel(key: string) {
  const labels: Record<string, string> = {
    height_cm: 'Altura',
    weight_kg: 'Peso',
    bmi: 'IMC',
    body_fat_percent: 'Gordura corporal',
    body_fat_kg: 'Gordura corporal em kg',
    muscle_mass_kg: 'Massa muscular',
    skeletal_muscle_kg: 'Músculo esquelético',
    fat_free_mass_kg: 'Massa magra',
    body_water_kg: 'Água corporal',
    protein_kg: 'Proteína',
    mineral_kg: 'Sal inorgânico',
    visceral_fat_level: 'Gordura visceral',
    basal_metabolic_rate: 'Taxa metabólica basal',
    subcutaneous_fat_percent: 'Gordura subcutanea',
    smi: 'SMI',
    body_age: 'Idade corporal',
    whr: 'WHR',
    target_weight_kg: 'Peso alvo',
    weight_control_kg: 'Controle de peso',
    fat_control_kg: 'Controle de gordura',
    muscle_control_kg: 'Controle muscular',
  }
  return labels[key] ?? key
}

function formatMetricValue(key: string, value: number) {
  const unitByKey: Record<string, string> = {
    height_cm: 'cm',
    weight_kg: 'kg',
    body_fat_percent: '%',
    body_fat_kg: 'kg',
    muscle_mass_kg: 'kg',
    skeletal_muscle_kg: 'kg',
    fat_free_mass_kg: 'kg',
    body_water_kg: 'kg',
    protein_kg: 'kg',
    mineral_kg: 'kg',
    basal_metabolic_rate: 'kcal',
    subcutaneous_fat_percent: '%',
    body_age: 'anos',
    target_weight_kg: 'kg',
    weight_control_kg: 'kg',
    fat_control_kg: 'kg',
    muscle_control_kg: 'kg',
  }
  return `${String(value).replace('.', ',')}${unitByKey[key] ? ` ${unitByKey[key]}` : ''}`
}

function formatDate(value: string) {
  return new Date(`${value}T12:00:00`).toLocaleDateString('pt-BR')
}
