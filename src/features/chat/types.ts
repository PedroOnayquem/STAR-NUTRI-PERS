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
    label: 'Pensamento Baixo',
    shortLabel: 'Baixo',
    description: 'Rapido e objetivo',
  },
  {
    id: 'medium',
    label: 'Pensamento Medio',
    shortLabel: 'Medio',
    description: 'Equilibrado',
  },
  {
    id: 'high',
    label: 'Pensamento Alto',
    shortLabel: 'Alto',
    description: 'Mais analitico',
  },
  {
    id: 'ultra',
    label: 'Pensamento Altissimo',
    shortLabel: 'Altissimo',
    description: 'Profundo e detalhado',
  },
]
