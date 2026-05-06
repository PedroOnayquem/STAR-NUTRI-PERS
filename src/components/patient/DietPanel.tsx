import { Plus, Utensils } from 'lucide-react'
import type { Diet } from '../../types'
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'

type DietPanelProps = {
  diet?: Diet
  onCreateDiet?: () => void
  readonly?: boolean
}

export function DietPanel({ diet, onCreateDiet, readonly = false }: DietPanelProps) {
  if (!diet) {
    return (
      <Card className="p-6 text-center">
        <Utensils className="mx-auto text-slate-400" size={28} />
        <h3 className="mt-3 text-lg font-bold">Nenhuma dieta ativa</h3>
        <p className="mx-auto mt-2 max-w-md text-sm text-slate-500 dark:text-slate-400">
          Cadastre uma dieta para que o paciente e a IA tenham um plano seguro
          como referencia.
        </p>
        {!readonly && (
          <Button className="mt-4" onClick={onCreateDiet} type="button">
            <Plus size={18} />
            Criar dieta demo
          </Button>
        )}
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      <Card className="p-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <h3 className="text-xl font-bold">{diet.title}</h3>
            <p className="mt-2 text-sm leading-6 text-slate-600 dark:text-slate-300">
              {diet.description}
            </p>
          </div>
          <div className="grid grid-cols-2 gap-2 text-sm sm:min-w-72">
            <Macro label="Kcal" value={diet.calories} />
            <Macro label="Agua" value={`${diet.waterGoalMl} ml`} />
            <Macro label="Proteina" value={`${diet.protein}g`} />
            <Macro label="Carbo" value={`${diet.carbs}g`} />
          </div>
        </div>
      </Card>

      <div className="grid gap-4 lg:grid-cols-3">
        {diet.meals.map((meal) => (
          <Card className="p-5" key={meal.id}>
            <div className="flex items-center justify-between gap-3">
              <h4 className="font-bold">{meal.mealName}</h4>
              <span className="text-sm font-semibold text-emerald-700 dark:text-emerald-300">
                {meal.mealTime}
              </span>
            </div>
            <div className="mt-4 space-y-2">
              {meal.foods.map((food) => (
                <div
                  className="flex items-center justify-between gap-3 rounded-lg bg-slate-50 px-3 py-2 text-sm dark:bg-slate-950"
                  key={`${meal.id}-${food.name}`}
                >
                  <span className="font-medium">{food.name}</span>
                  <span className="text-slate-500 dark:text-slate-400">
                    {food.quantity}
                  </span>
                </div>
              ))}
            </div>
            {meal.notes && (
              <p className="mt-3 text-sm text-slate-500 dark:text-slate-400">
                {meal.notes}
              </p>
            )}
          </Card>
        ))}
      </div>
    </div>
  )
}

function Macro({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg bg-slate-50 p-3 dark:bg-slate-950">
      <p className="text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">
        {label}
      </p>
      <p className="mt-1 font-bold">{value}</p>
    </div>
  )
}
