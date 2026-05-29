export type AiReasoningLevel = 'low' | 'medium' | 'high' | 'ultra'
export type ChatScope = 'nutritionist' | 'patient'

export const AI_REASONING_LEVELS: Array<{
  id: AiReasoningLevel
  label: string
  shortLabel: string
  description: string
}> = [
  {
    id: 'low',
    label: 'Raciocínio baixo',
    shortLabel: 'Baixo',
    description: 'Rápido e objetivo',
  },
  {
    id: 'medium',
    label: 'Raciocínio médio',
    shortLabel: 'Médio',
    description: 'Equilibrado',
  },
  {
    id: 'high',
    label: 'Raciocínio alto',
    shortLabel: 'Alto',
    description: 'Mais analítico',
  },
  {
    id: 'ultra',
    label: 'Raciocínio altíssimo',
    shortLabel: 'Altíssimo',
    description: 'Profundo e detalhado',
  },
]
