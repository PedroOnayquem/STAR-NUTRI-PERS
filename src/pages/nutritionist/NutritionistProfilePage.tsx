import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Camera, Save, Trash2, Upload } from 'lucide-react'
import { Badge } from '../../components/ui/Badge'
import { Button } from '../../components/ui/Button'
import { Card } from '../../components/ui/Card'
import { AppSelect } from '../../components/ui/FormControls'
import { Input, Textarea } from '../../components/ui/Input'
import { PageSkeleton } from '../../components/ui/Skeleton'
import { SectionHeader } from '../../components/ui/SectionHeader'
import { NutritionistAvatar } from '../../components/nutritionist/NutritionistAvatar'
import { useAuth } from '../../features/auth/useAuth'
import {
  getNutritionistWorkspace,
  updateNutritionistProfile,
} from '../../features/clinical/services/workspaceService'
import { nutritionistAvatarUrl } from '../../lib/storageImages'

const MAX_IMAGE_BYTES = 5 * 1024 * 1024
const ALLOWED_IMAGE_TYPES = new Set(['image/png', 'image/jpeg', 'image/webp'])

export function NutritionistProfilePage() {
  const { refreshProfile, session } = useAuth()
  const queryClient = useQueryClient()
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [form, setForm] = useState({
    bio: '',
    clinic_name: '',
    default_patient_trial_days: 7,
    phone: '',
    professional_name: '',
  })
  const [imageFile, setImageFile] = useState<File | null>(null)
  const [previewUrl, setPreviewUrl] = useState<string | null>(null)
  const [removeImage, setRemoveImage] = useState(false)
  const [imageFailed, setImageFailed] = useState(false)
  const [feedback, setFeedback] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const workspaceQuery = useQuery({
    queryKey: ['nutritionist-workspace'],
    queryFn: () => getNutritionistWorkspace(session),
    enabled: Boolean(session),
  })

  const nutritionist = workspaceQuery.data?.nutritionist
  const profile = workspaceQuery.data?.profile

  useEffect(() => {
    if (!nutritionist && !profile) return
    setForm({
      bio: nutritionist?.bio ?? '',
      clinic_name: nutritionist?.clinic_name ?? '',
      default_patient_trial_days: nutritionist?.default_patient_trial_days ?? 7,
      phone: nutritionist?.phone ?? profile?.phone ?? '',
      professional_name: nutritionist?.professional_name ?? profile?.full_name ?? '',
    })
  }, [nutritionist, profile])

  useEffect(() => {
    if (!imageFile) return
    const objectUrl = URL.createObjectURL(imageFile)
    setPreviewUrl(objectUrl)
    return () => URL.revokeObjectURL(objectUrl)
  }, [imageFile])

  const currentImageUrl = useMemo(() => {
    if (removeImage) return null
    return previewUrl || nutritionistAvatarUrl(nutritionist, profile)
  }, [nutritionist, previewUrl, profile, removeImage])

  useEffect(() => {
    setImageFailed(false)
  }, [currentImageUrl])

  const mutation = useMutation({
    mutationFn: () =>
      updateNutritionistProfile(session, {
        ...form,
        image: imageFile,
        remove_image: removeImage,
      }),
    onSuccess: () => {
      setFeedback('Perfil do nutricionista atualizado com sucesso.')
      setError(null)
      setImageFile(null)
      setPreviewUrl(null)
      setRemoveImage(false)
      queryClient.invalidateQueries({ queryKey: ['nutritionist-workspace'] })
      queryClient.invalidateQueries({ queryKey: ['nutritionist-dashboard'] })
      queryClient.invalidateQueries({ queryKey: ['patient-context'] })
      refreshProfile()
    },
    onError: (caught) => {
      setFeedback(null)
      setError(caught instanceof Error ? caught.message : 'Não foi possível salvar o perfil.')
    },
  })

  if (workspaceQuery.isLoading) return <PageSkeleton />
  if (workspaceQuery.error) throw workspaceQuery.error

  function handleFileChange(file: File | null) {
    setFeedback(null)
    setError(null)
    if (!file) return
    if (!ALLOWED_IMAGE_TYPES.has(file.type)) {
      setError('Envie uma imagem válida nos formatos PNG, JPG, JPEG ou WEBP.')
      return
    }
    if (file.size > MAX_IMAGE_BYTES) {
      setError('A imagem deve ter no máximo 5 MB.')
      return
    }
    setImageFile(file)
    setRemoveImage(false)
  }

  function handleRemoveImage() {
    setImageFile(null)
    setPreviewUrl(null)
    setRemoveImage(true)
    setFeedback(null)
    setError(null)
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  return (
    <div className="space-y-6">
      <SectionHeader
        description="Configure sua identidade profissional para personalizar a experiência dos seus pacientes."
        eyebrow={<Badge tone="green">Conta profissional</Badge>}
        title="Perfil do nutricionista"
      />

      <div className="grid gap-4 xl:grid-cols-[380px_minmax(0,1fr)]">
        <Card className="p-5" variant="glass">
          <div className="flex flex-col items-center text-center">
            <div className="relative">
              {currentImageUrl && !imageFailed ? (
                <div className="h-36 w-36 overflow-hidden rounded-3xl border border-white/20 bg-white shadow-xl dark:bg-slate-900">
                  <img
                    alt="Prévia da imagem profissional"
                    className="h-full w-full object-cover"
                    onError={() => setImageFailed(true)}
                    src={currentImageUrl}
                  />
                </div>
              ) : (
                <NutritionistAvatar
                  className="h-36 w-36 rounded-3xl text-4xl"
                  nutritionist={{
                    ...(nutritionist ?? {}),
                    avatar_path: null,
                    avatar_url: null,
                    logo_path: null,
                    logo_url: null,
                  } as NonNullable<typeof nutritionist>}
                  profile={profile ? { ...profile, avatar_url: null } : profile}
                />
              )}
              <div className="absolute -bottom-2 -right-2 rounded-2xl border border-white/70 bg-emerald-500 p-3 text-white shadow-lg dark:border-slate-950">
                <Camera size={18} />
              </div>
            </div>

            <h2 className="mt-5 text-lg font-black">
              {form.professional_name || profile?.full_name || 'Nutricionista'}
            </h2>
            <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
              {form.clinic_name || 'Clínica não informada'}
            </p>

            <input
              accept="image/png,image/jpeg,image/webp"
              className="hidden"
              onChange={(event) => handleFileChange(event.target.files?.[0] ?? null)}
              ref={fileInputRef}
              type="file"
            />

            <div className="mt-5 flex flex-wrap justify-center gap-2">
              <Button
                onClick={() => fileInputRef.current?.click()}
                type="button"
                variant="secondary"
              >
                <Upload size={18} />
                Alterar imagem
              </Button>
              <Button
                disabled={!currentImageUrl && !imageFile}
                onClick={handleRemoveImage}
                type="button"
                variant="ghost"
              >
                <Trash2 size={18} />
                Remover
              </Button>
            </div>

            <p className="mt-4 text-xs leading-5 text-slate-500 dark:text-slate-400">
              Use PNG, JPG, JPEG ou WEBP com até 5 MB. A imagem aparece no seu perfil e para pacientes vinculados.
            </p>
          </div>
        </Card>

        <Card className="p-5">
          <div className="grid gap-4 md:grid-cols-2">
            <Field label="Nome profissional">
              <Input
                placeholder="Dra. Ana Souza"
                value={form.professional_name}
                onChange={(event) => setForm({ ...form, professional_name: event.target.value })}
              />
            </Field>
            <Field label="Nome da clínica">
              <Input
                placeholder="Clínica Equilíbrio"
                value={form.clinic_name}
                onChange={(event) => setForm({ ...form, clinic_name: event.target.value })}
              />
            </Field>
            <Field label="Telefone">
              <Input
                placeholder="(11) 99999-9999"
                value={form.phone}
                onChange={(event) => setForm({ ...form, phone: event.target.value })}
              />
            </Field>
            <Field label="Especialidade">
              <Input disabled value={nutritionist?.specialty ?? 'Não informada'} />
            </Field>
            <Field label="Trial gratuito para novos pacientes">
              <AppSelect
                onChange={(value) => setForm({ ...form, default_patient_trial_days: Number(value) })}
                options={[
                  { label: '7 dias', value: '7' },
                  { label: '14 dias', value: '14' },
                  { label: '30 dias', value: '30' },
                ]}
                value={String(form.default_patient_trial_days)}
              />
            </Field>
            <div className="md:col-span-2">
              <Field label="Bio ou descrição profissional">
                <Textarea
                  maxLength={1000}
                  placeholder="Conte brevemente sobre sua atuação, abordagem clínica ou diferenciais profissionais."
                  value={form.bio}
                  onChange={(event) => setForm({ ...form, bio: event.target.value })}
                />
              </Field>
            </div>
          </div>

          <div className="mt-5 flex flex-wrap items-center gap-3">
            <Button
              disabled={mutation.isPending}
              onClick={() => mutation.mutate()}
              type="button"
              variant="premium"
            >
              <Save size={18} />
              {mutation.isPending ? 'Salvando...' : 'Salvar alterações'}
            </Button>
          </div>

          {feedback && (
            <p className="mt-4 rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-semibold text-emerald-700 dark:border-emerald-400/20 dark:bg-emerald-400/10 dark:text-emerald-200">
              {feedback}
            </p>
          )}
          {error && (
            <p className="mt-4 rounded-2xl border border-rose-200 bg-rose-50 px-4 py-3 text-sm font-semibold text-rose-700 dark:border-rose-400/20 dark:bg-rose-400/10 dark:text-rose-200">
              {error}
            </p>
          )}
        </Card>
      </div>
    </div>
  )
}

function Field({ children, label }: { children: ReactNode; label: string }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-bold text-slate-700 dark:text-slate-200">
        {label}
      </span>
      {children}
    </label>
  )
}
