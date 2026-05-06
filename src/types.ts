export type UserRole = 'admin' | 'nutritionist' | 'patient'

export type Profile = {
  id: string
  fullName: string
  email: string
  role: UserRole
  isActive: boolean
}

export type Nutritionist = {
  id: string
  userId: string
  crn: string
  specialty: string
  bio: string
}

export type Patient = {
  id: string
  userId: string
  nutritionistId: string
  fullName: string
  email: string
  birthDate: string
  gender: string
  objective: string
  notes: string
  isActive: boolean
}

export type HealthConditionType =
  | 'disease'
  | 'allergy'
  | 'food_restriction'
  | 'injury'
  | 'medication'
  | 'intolerance'
  | 'observation'

export type HealthCondition = {
  id: string
  patientId: string
  conditionType: HealthConditionType
  title: string
  description: string
  severity?: string
}

export type PatientMetric = {
  id: string
  patientId: string
  name: string
  value: string
  unit?: string
  recordedAt?: string
}

export type DietMeal = {
  id: string
  mealName: string
  mealTime: string
  foods: Array<{ name: string; quantity: string }>
  notes?: string
}

export type Diet = {
  id: string
  patientId: string
  nutritionistId: string
  title: string
  description: string
  calories: number
  protein: number
  carbs: number
  fats: number
  waterGoalMl: number
  isActive: boolean
  meals: DietMeal[]
}

export type WorkoutExercise = {
  id: string
  exerciseName: string
  muscleGroup: string
  sets: number
  reps: string
  restTime: string
  loadInfo?: string
  notes?: string
}

export type Workout = {
  id: string
  patientId: string
  nutritionistId: string
  title: string
  description: string
  frequencyPerWeek: number
  isActive: boolean
  exercises: WorkoutExercise[]
}

export type ChatMessage = {
  id: string
  sender: 'patient' | 'ai' | 'nutritionist'
  content: string
  createdAt: string
}

export type AppData = {
  profiles: Profile[]
  nutritionists: Nutritionist[]
  patients: Patient[]
  conditions: HealthCondition[]
  mainMetrics: PatientMetric[]
  variableMetrics: PatientMetric[]
  diets: Diet[]
  workouts: Workout[]
  chatMessages: ChatMessage[]
}
