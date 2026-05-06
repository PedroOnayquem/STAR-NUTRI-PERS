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
    ? `${context.diet.title}: ${context.diet.description}. Metas: ${context.diet.calories} kcal, ${context.diet.protein}g proteina, ${context.diet.carbs}g carboidratos, ${context.diet.fats}g gorduras.`
    : 'Sem dieta ativa cadastrada.'

  const workout = context.workout
    ? `${context.workout.title}: ${context.workout.description}. Frequencia: ${context.workout.frequencyPerWeek}x por semana.`
    : 'Sem treino ativo cadastrado.'

  return {
    model: 'GLM 5.0',
    systemPrompt: [
      'Voce e um assistente de acompanhamento nutricional.',
      'Voce nao substitui o nutricionista nem um medico.',
      'Voce deve responder com base no plano cadastrado pelo nutricionista.',
      'Voce nao deve prescrever dieta, treino, medicamento ou diagnostico.',
      'Se houver sintomas graves, oriente procurar atendimento medico.',
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
    return 'Eu nao posso alterar sua dieta, treino ou sugerir medicacao. Posso te ajudar a entender o plano atual e organizar duvidas para sua nutricionista avaliar com seguranca.'
  }

  if (lowered.includes('dor forte') || lowered.includes('desmaio')) {
    return 'Esse relato pode exigir avaliacao presencial. Procure atendimento medico imediatamente e avise sua nutricionista quando estiver seguro.'
  }

  const dietHint = activeDiet
    ? `Seu plano ativo e "${activeDiet.title}", com meta de ${activeDiet.calories} kcal e ${activeDiet.waterGoalMl} ml de agua.`
    : 'Ainda nao encontrei uma dieta ativa cadastrada.'

  const workoutHint = activeWorkout
    ? `Seu treino ativo e "${activeWorkout.title}", planejado para ${activeWorkout.frequencyPerWeek}x por semana.`
    : 'Ainda nao encontrei um treino ativo cadastrado.'

  return `${dietHint} ${workoutHint} Minha orientacao e seguir o que foi prescrito, registrar suas metricas de hoje e levar qualquer dificuldade recorrente para a nutricionista ajustar o plano.`
}

function formatMetric(metric: PatientMetric) {
  return `${metric.name}: ${metric.value}${metric.unit ? ` ${metric.unit}` : ''}`
}
