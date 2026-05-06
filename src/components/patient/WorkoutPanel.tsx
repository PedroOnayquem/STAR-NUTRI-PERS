import { Dumbbell, Plus } from 'lucide-react'
import type { Workout } from '../../types'
import { Button } from '../ui/Button'
import { Card } from '../ui/Card'

type WorkoutPanelProps = {
  workout?: Workout
  onCreateWorkout?: () => void
  readonly?: boolean
}

export function WorkoutPanel({
  workout,
  onCreateWorkout,
  readonly = false,
}: WorkoutPanelProps) {
  if (!workout) {
    return (
      <Card className="p-6 text-center">
        <Dumbbell className="mx-auto text-slate-400" size={28} />
        <h3 className="mt-3 text-lg font-bold">Nenhum treino ativo</h3>
        <p className="mx-auto mt-2 max-w-md text-sm text-slate-500 dark:text-slate-400">
          Cadastre um treino para orientar o acompanhamento e limitar as
          respostas da IA ao plano definido.
        </p>
        {!readonly && (
          <Button className="mt-4" onClick={onCreateWorkout} type="button">
            <Plus size={18} />
            Criar treino demo
          </Button>
        )}
      </Card>
    )
  }

  return (
    <Card className="p-5">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h3 className="text-xl font-bold">{workout.title}</h3>
          <p className="mt-2 text-sm leading-6 text-slate-600 dark:text-slate-300">
            {workout.description}
          </p>
        </div>
        <span className="rounded-full bg-sky-50 px-3 py-1 text-sm font-bold text-sky-700 dark:bg-sky-950 dark:text-sky-300">
          {workout.frequencyPerWeek}x / semana
        </span>
      </div>

      <div className="mt-5 overflow-x-auto">
        <table className="w-full min-w-[680px] text-left text-sm">
          <thead className="text-xs uppercase text-slate-500 dark:text-slate-400">
            <tr>
              <th className="py-3">Exercicio</th>
              <th>Grupo</th>
              <th>Series</th>
              <th>Reps</th>
              <th>Descanso</th>
              <th>Observacao</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
            {workout.exercises.map((exercise) => (
              <tr key={exercise.id}>
                <td className="py-3 font-semibold">{exercise.exerciseName}</td>
                <td>{exercise.muscleGroup}</td>
                <td>{exercise.sets}</td>
                <td>{exercise.reps}</td>
                <td>{exercise.restTime}</td>
                <td className="text-slate-500 dark:text-slate-400">
                  {exercise.notes ?? exercise.loadInfo ?? '-'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  )
}
