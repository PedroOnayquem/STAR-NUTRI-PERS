import { useEffect, useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import {
  ChevronLeft,
  ChevronRight,
  Database,
  Loader2,
  Search,
  Utensils,
} from 'lucide-react'
import { Button } from '../../components/ui/Button'
import { EmptyState } from '../../components/ui/EmptyState'
import { AppSelect } from '../../components/ui/FormControls'
import { Input } from '../../components/ui/Input'
import { SectionHeader } from '../../components/ui/SectionHeader'
import { cn } from '../../lib/utils'
import { formatNutrient } from '../../features/taco/nutrition'
import { listTacoCategories, searchTacoFoods } from '../../features/taco/services/tacoService'
import type { TacoFoodRecord } from '../../features/taco/types'

const PAGE_SIZE = 18

const MAIN_NUTRIENTS = [
  { key: 'energy_kcal', label: 'Energia', unit: 'kcal' },
  { key: 'protein_g', label: 'Proteínas', unit: 'g' },
  { key: 'carbohydrate_g', label: 'Carboidratos', unit: 'g' },
  { key: 'lipid_g', label: 'Lipídios', unit: 'g' },
  { key: 'fiber_g', label: 'Fibras', unit: 'g' },
  { key: 'sodium_mg', label: 'Sódio', unit: 'mg' },
] satisfies Array<{ key: keyof TacoFoodRecord; label: string; unit: string }>

const DETAIL_NUTRIENTS = [
  ...MAIN_NUTRIENTS,
  { key: 'moisture_g', label: 'Umidade', unit: 'g' },
  { key: 'calcium_mg', label: 'Cálcio', unit: 'mg' },
  { key: 'magnesium_mg', label: 'Magnésio', unit: 'mg' },
  { key: 'manganese_mg', label: 'Manganês', unit: 'mg' },
  { key: 'phosphorus_mg', label: 'Fósforo', unit: 'mg' },
  { key: 'iron_mg', label: 'Ferro', unit: 'mg' },
  { key: 'potassium_mg', label: 'Potássio', unit: 'mg' },
  { key: 'copper_mg', label: 'Cobre', unit: 'mg' },
  { key: 'zinc_mg', label: 'Zinco', unit: 'mg' },
  { key: 'retinol_mcg', label: 'Retinol', unit: 'mcg' },
  { key: 're_mcg', label: 'RE', unit: 'mcg' },
  { key: 'rae_mcg', label: 'RAE', unit: 'mcg' },
  { key: 'thiamine_mg', label: 'Tiamina', unit: 'mg' },
  { key: 'riboflavin_mg', label: 'Riboflavina', unit: 'mg' },
  { key: 'pyridoxine_mg', label: 'Piridoxina', unit: 'mg' },
  { key: 'niacin_mg', label: 'Niacina', unit: 'mg' },
  { key: 'vitamin_c_mg', label: 'Vitamina C', unit: 'mg' },
] satisfies Array<{ key: keyof TacoFoodRecord; label: string; unit: string }>

export function TacoPage() {
  const [query, setQuery] = useState('')
  const [debouncedQuery, setDebouncedQuery] = useState('')
  const [category, setCategory] = useState('')
  const [page, setPage] = useState(1)
  const [selectedFoodId, setSelectedFoodId] = useState<string | null>(null)

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      setDebouncedQuery(query)
      setPage(1)
    }, 260)
    return () => window.clearTimeout(timeout)
  }, [query])

  const categoriesQuery = useQuery({
    queryKey: ['taco-categories'],
    queryFn: listTacoCategories,
  })

  const foodsQuery = useQuery({
    queryKey: ['taco-foods', debouncedQuery, category, page],
    queryFn: () => searchTacoFoods({
      category: category || null,
      page,
      pageSize: PAGE_SIZE,
      query: debouncedQuery,
    }),
  })

  const foods = useMemo(() => foodsQuery.data?.foods ?? [], [foodsQuery.data?.foods])
  const total = foodsQuery.data?.count ?? 0
  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE))
  const selectedFood = foods.find((food) => food.id === selectedFoodId) ?? foods[0] ?? null
  const categoryOptions = useMemo(
    () => [
      { label: 'Todas as categorias', value: 'all' },
      ...(categoriesQuery.data ?? []).map((item) => ({ label: item, value: item })),
    ],
    [categoriesQuery.data],
  )

  return (
    <div className="space-y-6">
      <SectionHeader
        eyebrow="Base de alimentos"
        title="Tabela TACO"
        description="Composição nutricional oficial da TACO por 100 g de parte comestível."
      />

      <section className="overflow-hidden rounded-2xl border border-cyan-300/15 bg-[#061020]/95 text-slate-100 shadow-[0_28px_90px_rgba(2,6,23,0.24)]">
        <div className="border-b border-cyan-300/10 bg-[linear-gradient(135deg,rgba(14,165,233,0.12),rgba(16,185,129,0.10),rgba(2,6,23,0))] p-4">
          <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_280px]">
            <label className="relative block">
              <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-cyan-100/65" size={18} />
              <Input
                className="border-cyan-300/15 bg-slate-950/55 pl-10 text-slate-50 placeholder:text-slate-500 focus:border-cyan-300/45 focus:ring-cyan-300/10"
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Buscar alimento"
                value={query}
              />
            </label>
            <AppSelect
              onChange={(value) => {
                setCategory(value === 'all' ? '' : value)
                setPage(1)
              }}
              options={categoryOptions}
              value={category || 'all'}
            />
          </div>
        </div>

        <div className="grid min-h-[620px] lg:grid-cols-[minmax(0,1.05fr)_minmax(360px,0.95fr)]">
          <div className="min-h-0 border-b border-cyan-300/10 lg:border-b-0 lg:border-r">
            {foodsQuery.isLoading ? (
              <LoadingPanel />
            ) : foodsQuery.error ? (
              <EmptyState
                className="m-4 border-rose-300/20 bg-rose-500/5 text-slate-100"
                description={foodsQuery.error.message}
                icon={<Database size={22} />}
                title="Não foi possível carregar a TACO"
              />
            ) : foods.length === 0 ? (
              <EmptyState
                className="m-4 border-cyan-300/15 bg-slate-950/25 text-slate-100"
                description="Nenhum alimento encontrado para os filtros atuais."
                icon={<Utensils size={22} />}
                title="Sem resultados"
              />
            ) : (
              <div className="premium-scrollbar max-h-[620px] overflow-y-auto p-2">
                <div className="space-y-1">
                  {foods.map((food) => (
                    <FoodRow
                      food={food}
                      key={food.id}
                      onSelect={() => setSelectedFoodId(food.id)}
                      selected={selectedFood?.id === food.id}
                    />
                  ))}
                </div>
              </div>
            )}

            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-cyan-300/10 px-4 py-3 text-sm text-slate-400">
              <span>
                {total > 0 ? `${total.toLocaleString('pt-BR')} alimentos` : 'Nenhum alimento'}
              </span>
              <div className="flex items-center gap-2">
                <Button
                  className="h-9 w-9 rounded-full border-cyan-300/15 bg-slate-950/40 text-slate-100"
                  disabled={page <= 1 || foodsQuery.isFetching}
                  onClick={() => setPage((current) => Math.max(1, current - 1))}
                  size="icon"
                  type="button"
                  variant="secondary"
                >
                  <ChevronLeft size={16} />
                </Button>
                <span className="min-w-20 text-center text-xs font-bold text-slate-300">
                  {page} / {pageCount}
                </span>
                <Button
                  className="h-9 w-9 rounded-full border-cyan-300/15 bg-slate-950/40 text-slate-100"
                  disabled={page >= pageCount || foodsQuery.isFetching}
                  onClick={() => setPage((current) => Math.min(pageCount, current + 1))}
                  size="icon"
                  type="button"
                  variant="secondary"
                >
                  <ChevronRight size={16} />
                </Button>
              </div>
            </div>
          </div>

          <FoodDetails food={selectedFood} loading={foodsQuery.isFetching && foods.length > 0} />
        </div>
      </section>
    </div>
  )
}

function FoodRow({
  food,
  onSelect,
  selected,
}: {
  food: TacoFoodRecord
  onSelect: () => void
  selected: boolean
}) {
  return (
    <button
      className={cn(
        'w-full rounded-xl px-3 py-3 text-left transition',
        selected
          ? 'bg-cyan-300/10 text-white shadow-[inset_0_0_0_1px_rgba(34,211,238,0.18)]'
          : 'text-slate-300 hover:bg-cyan-300/[0.07] hover:text-white',
      )}
      onClick={onSelect}
      type="button"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-sm font-black">{food.name}</p>
          <p className="mt-1 truncate text-xs text-slate-500">
            {food.category || 'Sem categoria'}{food.code ? ` - ${food.code}` : ''}
          </p>
        </div>
        <span className="shrink-0 rounded-full border border-emerald-300/15 bg-emerald-300/10 px-2.5 py-1 text-xs font-black text-emerald-200">
          {formatNutrient(food.energy_kcal, 'kcal')}
        </span>
      </div>
      <div className="mt-3 grid grid-cols-3 gap-2 text-xs sm:grid-cols-5">
        <MiniNutrient label="P" value={food.protein_g} unit="g" />
        <MiniNutrient label="C" value={food.carbohydrate_g} unit="g" />
        <MiniNutrient label="G" value={food.lipid_g} unit="g" />
        <MiniNutrient label="Fibra" value={food.fiber_g} unit="g" />
        <MiniNutrient label="Sódio" value={food.sodium_mg} unit="mg" />
      </div>
    </button>
  )
}

function FoodDetails({
  food,
  loading,
}: {
  food: TacoFoodRecord | null
  loading: boolean
}) {
  if (!food) {
    return (
      <div className="flex min-h-[420px] items-center justify-center p-4">
        <EmptyState
          className="w-full border-cyan-300/15 bg-slate-950/25 text-slate-100"
          description="Pesquise e selecione um alimento."
          icon={<Utensils size={22} />}
          title="Alimento"
        />
      </div>
    )
  }

  return (
    <aside className="relative min-h-0 p-5">
      {loading && (
        <div className="absolute right-5 top-5 rounded-full border border-cyan-300/15 bg-slate-950/70 p-2 text-cyan-100">
          <Loader2 className="animate-spin" size={16} />
        </div>
      )}
      <div>
        <p className="text-xs font-black uppercase text-emerald-300">
          Valores por 100g
        </p>
        <h2 className="mt-2 text-2xl font-black tracking-normal text-white">
          {food.name}
        </h2>
        <p className="mt-2 text-sm text-slate-400">
          {food.category || 'Sem categoria'}{food.code ? ` - código ${food.code}` : ''}
        </p>
        <p className="mt-1 text-xs text-slate-500">
          {food.source} · {food.source_edition} · {food.publication_year}
        </p>
      </div>

      <div className="mt-6 grid grid-cols-2 gap-3">
        {MAIN_NUTRIENTS.map((nutrient) => (
          <div
            className="rounded-xl border border-cyan-300/10 bg-slate-950/35 p-3"
            key={nutrient.key}
          >
            <p className="text-xs text-slate-500">{nutrient.label}</p>
            <p className="mt-1 text-lg font-black text-slate-50">
              {formatNutrient(food[nutrient.key] as number | null, nutrient.unit)}
            </p>
          </div>
        ))}
      </div>

      <div className="mt-6 overflow-hidden rounded-xl border border-cyan-300/10">
        <div className="grid grid-cols-[1fr_110px] bg-slate-950/55 px-3 py-2 text-xs font-black uppercase text-slate-500">
          <span>Nutriente</span>
          <span className="text-right">100g</span>
        </div>
        <div className="premium-scrollbar max-h-[300px] overflow-y-auto">
          {DETAIL_NUTRIENTS.map((nutrient) => (
            <div
              className="grid grid-cols-[1fr_110px] border-t border-cyan-300/10 px-3 py-2 text-sm"
              key={nutrient.key}
            >
              <span className="text-slate-300">{nutrient.label}</span>
              <span className="text-right font-bold text-slate-100">
                {formatNutrient(food[nutrient.key] as number | null, nutrient.unit)}
              </span>
            </div>
          ))}
        </div>
      </div>
    </aside>
  )
}

function MiniNutrient({
  label,
  unit,
  value,
}: {
  label: string
  unit: string
  value: number | null
}) {
  return (
    <span className="rounded-lg bg-slate-950/35 px-2 py-1 text-slate-400">
      <span className="font-black text-slate-200">{label}</span> {formatNutrient(value, unit)}
    </span>
  )
}

function LoadingPanel() {
  return (
    <div className="flex min-h-[420px] items-center justify-center text-cyan-100">
      <Loader2 className="animate-spin" size={24} />
    </div>
  )
}
