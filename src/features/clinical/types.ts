export type UserRole = 'admin' | 'nutritionist' | 'patient'

export type ProfileSummary = {
  id: string
  full_name: string
  email: string
  role: UserRole
  avatar_url: string | null
  phone: string | null
  is_active: boolean
  created_at?: string | null
}

export type NutritionistRecord = {
  id: string
  user_id: string
  crn: string | null
  avatar_path: string | null
  avatar_url: string | null
  logo_path: string | null
  logo_url: string | null
  clinic_name: string | null
  professional_name: string | null
  phone: string | null
  bio: string | null
  default_patient_trial_days: number
  specialty: string | null
  created_at?: string | null
}

export type PatientRecord = {
  id: string
  user_id: string
  nutritionist_id: string
  access_status: 'TRIAL' | 'ACTIVE' | 'EXPIRED'
  activated_at: string | null
  birth_date: string | null
  expired_at: string | null
  gender: string | null
  has_premium_access?: boolean
  objective: string | null
  notes: string | null
  is_active: boolean
  trial_days: number | null
  trial_days_remaining: number
  trial_ends_at: string | null
  trial_expired_message?: string | null
  trial_started_at: string | null
  created_at?: string | null
  updated_at?: string | null
  profile?: ProfileSummary | null
}

export type HealthConditionType =
  | 'disease'
  | 'allergy'
  | 'food_restriction'
  | 'injury'
  | 'medication'
  | 'intolerance'
  | 'observation'

export type HealthConditionRecord = {
  id: string
  patient_id: string
  condition_type: HealthConditionType
  title: string
  description: string
  injury_local: string | null
  notes: string | null
  origin: string | null
  recommendations: string | null
  severity: string | null
  started_at: string | null
  created_at?: string | null
}

export type MetricRecord = {
  id: string
  patient_id: string
  name: string
  value: string
  unit: string | null
  defined_by?: string | null
  recorded_at?: string | null
  source_type?: string | null
  source_import_id?: string | null
  created_at?: string | null
}

export type DietMealFood = {
  calories?: number | null
  carbohydrate_g?: number | null
  carbs_g?: number | null
  energy_kcal?: number | null
  fats_g?: number | null
  fiber_g?: number | null
  lipid_g?: number | null
  name: string
  notes?: string
  protein_g?: number | null
  quantity: string
  quantity_g?: number | null
  sodium_mg?: number | null
  taco_food_id?: string | null
}

export type DietMealItemRecord = {
  carbohydrate_g: number | null
  created_at?: string | null
  custom_food_name: string | null
  energy_kcal: number | null
  fiber_g: number | null
  id: string
  lipid_g: number | null
  meal_id: string
  protein_g: number | null
  quantity_g: number
  sodium_mg: number | null
  taco_food_id: string | null
  updated_at?: string | null
}

export type DietMealRecord = {
  id: string
  diet_id: string
  meal_name: string
  meal_time: string | null
  foods: DietMealFood[]
  items?: DietMealItemRecord[]
  notes: string | null
}

export type DietRecord = {
  id: string
  patient_id: string
  nutritionist_id: string
  title: string
  description: string | null
  calories: number | null
  protein: number | null
  carbs: number | null
  fats: number | null
  water_goal_ml: number | null
  is_active: boolean
  created_at?: string | null
  updated_at?: string | null
  meals?: DietMealRecord[]
}

export type WorkoutExerciseRecord = {
  id: string
  workout_id: string
  exercise_name: string
  muscle_group: string | null
  sets: number | null
  reps: string | null
  rest_time: string | null
  load_info: string | null
  notes: string | null
}

export type WorkoutRecord = {
  id: string
  patient_id: string
  nutritionist_id: string
  title: string
  description: string | null
  frequency_per_week: number | null
  is_active: boolean
  created_at?: string | null
  updated_at?: string | null
  exercises?: WorkoutExerciseRecord[]
}

export type ChatSessionRecord = {
  id: string
  chat_scope?: 'general' | 'patient'
  patient_id: string | null
  nutritionist_id?: string
  title: string | null
  created_at: string
  updated_at: string | null
}

export type ChatMessageRecord = {
  id: string
  chat_id: string
  sender: 'patient' | 'ai' | 'nutritionist'
  content: string
  metadata: Record<string, unknown> | null
  created_at: string
}

export type AppointmentType =
  | 'acompanhamento'
  | 'consulta'
  | 'reuniao'
  | 'avaliacao'
  | 'retorno'
  | 'revisao_dieta'
  | 'revisao_treino'
  | 'outro'

export type AppointmentStatus =
  | 'agendado'
  | 'confirmado'
  | 'concluido'
  | 'cancelado'
  | 'faltou'

export type PatientAppointmentRecord = {
  id: string
  patient_id: string
  patient_user_id: string
  nutritionist_id: string
  title: string
  type: AppointmentType
  description: string | null
  date: string
  start_time: string
  end_time: string | null
  location: string | null
  meeting_link: string | null
  status: AppointmentStatus
  notes: string | null
  created_at?: string | null
  updated_at?: string | null
}

export type NotificationType =
  | 'appointment_created'
  | 'appointment_updated'
  | 'appointment_cancelled'
  | 'appointment_reminder'

export type NotificationRecord = {
  id: string
  user_id: string
  patient_id: string | null
  appointment_id: string | null
  title: string
  message: string
  type: NotificationType
  read: boolean
  created_at: string
}

export type PatientImportRecord = {
  id: string
  patient_id: string | null
  nutritionist_id: string
  file_url: string | null
  file_path?: string | null
  source_type: 'bioimpedance_report' | 'bioimpedance_pdf' | string
  file_type: 'pdf' | 'jpg' | 'jpeg' | 'png' | null
  mime_type?: string | null
  original_file_name?: string | null
  file_size_bytes?: number | null
  error_message?: string | null
  files?: PatientImportFileRecord[]
  extracted_payload: Record<string, unknown>
  confidence_payload: Record<string, unknown>
  status: 'processed' | 'linked' | 'failed'
  created_at: string
  updated_at?: string | null
}

export type PatientImportFileRecord = {
  id: string
  import_id: string
  file_url: string | null
  file_type: 'pdf' | 'jpg' | 'jpeg' | 'png' | null
  mime_type: string | null
  original_file_name: string | null
  file_size_bytes: number | null
  extracted_text?: string | null
  order_index: number | null
  created_at: string
}

export type PatientContext = {
  access?: {
    can_use_ai_chat: boolean
    expired_message: string | null
    has_premium_access: boolean
    status: 'TRIAL' | 'ACTIVE' | 'EXPIRED'
    trial_days_remaining: number
  }
  patient: PatientRecord
  profile: ProfileSummary | null
  nutritionist: NutritionistRecord | null
  main_metrics: MetricRecord[]
  variable_metrics: MetricRecord[]
  conditions: HealthConditionRecord[]
  diets: DietRecord[]
  workouts: WorkoutRecord[]
  nutritionist_chats: ChatSessionRecord[]
  patient_chats: ChatSessionRecord[]
  appointments: PatientAppointmentRecord[]
  imports: PatientImportRecord[]
  recent_professional_messages: ChatMessageRecord[]
  recent_personal_messages: ChatMessageRecord[]
}

export type NutritionistWorkspace = {
  nutritionist: NutritionistRecord
  profile: ProfileSummary
  patients: PatientRecord[]
}

export type DashboardAlert = {
  id: string
  type: 'evolution' | 'diet' | 'condition' | 'appointment'
  tone: 'green' | 'blue' | 'amber' | 'red' | 'slate'
  title: string
  description: string
  patient_id: string
  patient_name: string
  date: string | null
}

export type DashboardPatientSummary = {
  id: string
  name: string
  objective: string | null
  status: 'TRIAL' | 'ACTIVE' | 'EXPIRED'
  is_active: boolean
  trial_days_remaining: number
  last_update_at: string | null
  next_appointment_at: string | null
  alert: string | null
}

export type NutritionistDashboard = {
  nutritionist: NutritionistRecord
  profile: ProfileSummary
  stats: {
    active_patients: number
    activated_patients: number
    appointments_today: number
    active_diets: number
    expired_patients: number
    important_alerts: number
    trial_patients: number
  }
  recent_patients: DashboardPatientSummary[]
  alerts: DashboardAlert[]
}

export type AdminWorkspace = {
  profiles: ProfileSummary[]
  nutritionists: NutritionistRecord[]
  patients: PatientRecord[]
  stats: {
    users: number
    nutritionists: number
    patients: number
    active_patients: number
    diets: number
    workouts: number
    chat_messages: number
  }
}
