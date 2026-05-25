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
  bio: string | null
  specialty: string | null
  created_at?: string | null
}

export type PatientRecord = {
  id: string
  user_id: string
  nutritionist_id: string
  birth_date: string | null
  gender: string | null
  objective: string | null
  notes: string | null
  is_active: boolean
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
  created_at?: string | null
}

export type DietMealRecord = {
  id: string
  diet_id: string
  meal_name: string
  meal_time: string | null
  foods: Array<{ name: string; quantity: string; notes?: string }>
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
  patient_id: string
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

export type PatientContext = {
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
  recent_professional_messages: ChatMessageRecord[]
  recent_personal_messages: ChatMessageRecord[]
}

export type NutritionistWorkspace = {
  nutritionist: NutritionistRecord
  patients: PatientRecord[]
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
