import assert from 'node:assert/strict'
import { mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import test from 'node:test'
import * as XLSX from 'xlsx'
import { normalizeSearchText, parseOfficialTacoWorkbook, TACO_SOURCE } from './import-taco'

test('normaliza nomes em português para a chave de pesquisa', () => {
  assert.equal(normalizeSearchText('  Arroz, tipo 1, cozido  '), 'arroz tipo 1 cozido')
  assert.equal(normalizeSearchText('Açaí com açúcar'), 'acai com acucar')
})

test('importa as três abas sem transformar traço ou NA em zero', () => {
  const directory = mkdtempSync(join(tmpdir(), 'star-nutri-taco-'))
  const file = join(directory, 'Taco-4a-Edicao.xlsx')
  try {
    const mainRows: unknown[][] = [
      [],
      ['Número do', null, 'Umidade', 'Energia'],
      ['Alimento', 'Descrição dos alimentos', '(%)', '(kcal)'],
      ['Cereais e derivados'],
    ]
    for (let code = 1; code <= 597; code += 1) {
      const row = Array.from({ length: 29 }, () => null) as unknown[]
      row[0] = code
      row[1] = code === 1 ? 'Arroz, integral, cozido' : `Alimento ${code}`
      row[2] = 70
      row[3] = code === 1 ? 124 : 100
      row[5] = 2.6
      row[7] = code === 1 ? 'NA' : 0
      row[8] = 25.8
      row[25] = code === 1 ? 'Tr' : 0.1
      mainRows.push(row)
    }

    const fattyRow = Array.from({ length: 25 }, () => null) as unknown[]
    fattyRow[0] = 1
    fattyRow[1] = 'Arroz, integral, cozido'
    fattyRow[2] = 0.3
    fattyRow[6] = 'Tr'

    const aminoRow = Array.from({ length: 21 }, () => null) as unknown[]
    aminoRow[0] = 1
    aminoRow[1] = 'Arroz, integral, cozido'
    aminoRow[2] = 0.01

    const workbook = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(workbook, XLSX.utils.aoa_to_sheet(mainRows), 'CMVCol taco3')
    XLSX.utils.book_append_sheet(workbook, XLSX.utils.aoa_to_sheet([[], [], [], fattyRow]), 'AGtaco3')
    XLSX.utils.book_append_sheet(workbook, XLSX.utils.aoa_to_sheet([[], [], [], aminoRow]), 'Aminoácidos TACO3')
    XLSX.writeFile(workbook, file)

    const parsed = parseOfficialTacoWorkbook(file)
    const rice = parsed.foods[0]
    assert.equal(parsed.foods.length, 597)
    assert.equal(rice.category, 'Cereais e derivados')
    assert.equal(rice.energy_kcal, 124)
    assert.equal(rice.cholesterol_mg, null)
    assert.equal(rice.riboflavin_mg, null)
    assert.equal(rice.source_edition, TACO_SOURCE.edition)

    const cholesterol = parsed.nutrients.find((item) => item.source_key.endsWith(':1') && item.nutrient_code === 'cholesterol_mg')
    const riboflavin = parsed.nutrients.find((item) => item.source_key.endsWith(':1') && item.nutrient_code === 'riboflavin_mg')
    assert.equal(cholesterol?.value_status, 'not_applicable')
    assert.equal(cholesterol?.source_value, 'NA')
    assert.equal(riboflavin?.value_status, 'trace')
    assert.equal(riboflavin?.source_value, 'Tr')
  } finally {
    rmSync(directory, { force: true, recursive: true })
  }
})
