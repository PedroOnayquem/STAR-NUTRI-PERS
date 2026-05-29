import type {
  ChatMessage,
  Diet,
  HealthCondition,
  Patient,
  PatientMetric,
  Workout,
} from '../types'

type PatientAiContext = {
  patient: Patient
  diet?: Diet
  workout?: Workout
  mainMetrics: PatientMetric[]
  variableMetrics: PatientMetric[]
  conditions: HealthCondition[]
  recentMessages: ChatMessage[]
}

export function buildPatientAiContext(context: PatientAiContext) {
  const diet = context.diet
    ? `${context.diet.title}: ${context.diet.description}. Metas: ${context.diet.calories} kcal, ${context.diet.protein}g proteína, ${context.diet.carbs}g carboidratos, ${context.diet.fats}g gorduras.`
    : 'Sem dieta ativa cadastrada.'

  const workout = context.workout
    ? `${context.workout.title}: ${context.workout.description}. Frequência: ${context.workout.frequencyPerWeek}x por semana.`
    : 'Sem treino ativo cadastrado.'

  return {
    model: 'Star Nutri IA',
    systemPrompt: [
      'Você é um assistente de acompanhamento nutricional.',
      'Você não substitui o nutricionista nem um médico.',
      'Você deve responder com base no plano cadastrado pelo nutricionista.',
      'Você não deve prescrever dieta, treino, medicamento ou diagnóstico.',
      'Se houver sintomas graves, oriente procurar atendimento médico.',
    ],
    patient: {
      name: context.patient.fullName,
      objective: context.patient.objective,
      notes: context.patient.notes,
    },
    diet,
    workout,
    mainMetrics: context.mainMetrics.map(formatMetric),
    variableMetrics: context.variableMetrics.map(formatMetric),
    conditions: context.conditions.map(
      (condition) =>
        `${condition.conditionType}: ${condition.title} - ${condition.description}`,
    ),
    recentHistory: context.recentMessages.map(
      (message) => `${message.sender}: ${message.content}`,
    ),
  }
}

export function generateGuardedAiReply(context: PatientAiContext, content: string) {
  const lowered = content.toLowerCase()
  const activeDiet = context.diet
  const activeWorkout = context.workout

  if (
    lowered.includes('trocar dieta') ||
    lowered.includes('nova dieta') ||
    lowered.includes('mudar meu treino') ||
    lowered.includes('remedio')
  ) {
    return 'Eu não posso alterar sua dieta, treino ou sugerir medicação. Posso te ajudar a entender o plano atual e organizar dúvidas para sua nutricionista avaliar com segurança.'
  }

  if (lowered.includes('dor forte') || lowered.includes('desmaio')) {
    return 'Esse relato pode exigir avaliação presencial. Procure atendimento médico imediatamente e avise sua nutricionista quando estiver seguro.'
  }

  const dietHint = activeDiet
    ? `Seu plano ativo é "${activeDiet.title}", com meta de ${activeDiet.calories} kcal e ${activeDiet.waterGoalMl} ml de água.`
    : 'Ainda não encontrei uma dieta ativa cadastrada.'

  const workoutHint = activeWorkout
    ? `Seu treino ativo é "${activeWorkout.title}", planejado para ${activeWorkout.frequencyPerWeek}x por semana.`
    : 'Ainda não encontrei um treino ativo cadastrado.'

  return `${dietHint} ${workoutHint} Minha orientação é seguir o que foi prescrito, registrar suas métricas de hoje e levar qualquer dificuldade recorrente para a nutricionista ajustar o plano.`
}

function formatMetric(metric: PatientMetric) {
  return `${metric.name}: ${metric.value}${metric.unit ? ` ${metric.unit}` : ''}`
}
