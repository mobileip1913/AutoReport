import { ref } from 'vue'
import { api } from '@/api/client'

export interface CatalogFile {
  keyword: string
  label?: string
  file_label?: string
}

export function useCatalog(dataSourceId: () => number | null) {
  const files = ref<CatalogFile[]>([])
  const sheetsByFile = ref<Record<string, string[]>>({})
  const columnsByKey = ref<Record<string, string[]>>({})

  async function loadFiles() {
    const id = dataSourceId()
    if (!id) return
    const { data } = await api.get(`/api/data-sources/${id}/catalog`)
    const tree = data.files ?? data.tree?.files ?? []
    files.value = tree.map((f: string | CatalogFile) =>
      typeof f === 'string' ? { keyword: f, label: f } : f,
    )
  }

  async function loadSheets(fileKeyword: string) {
    const id = dataSourceId()
    if (!id || !fileKeyword) return []
    if (sheetsByFile.value[fileKeyword]) return sheetsByFile.value[fileKeyword]
    const { data } = await api.get(`/api/data-sources/${id}/schema`, {
      params: { file: fileKeyword },
    })
    const sheets = (data.sheets ?? []) as string[]
    sheetsByFile.value[fileKeyword] = sheets
    return sheets
  }

  async function loadColumns(fileKeyword: string, sheetName: string) {
    const id = dataSourceId()
    if (!id || !fileKeyword || !sheetName) return []
    const key = `${fileKeyword}::${sheetName}`
    if (columnsByKey.value[key]) return columnsByKey.value[key]
    const { data } = await api.get(`/api/data-sources/${id}/schema`, {
      params: { file: fileKeyword, sheet: sheetName },
    })
    const cols = (data.columns ?? []) as string[]
    columnsByKey.value[key] = cols
    return cols
  }

  function fileOptions() {
    return files.value.map((f) => ({
      label: f.label ?? f.file_label ?? f.keyword,
      value: f.keyword,
    }))
  }

  async function sheetOptions(fileKeyword: string) {
    const sheets = await loadSheets(fileKeyword)
    return sheets.map((s) => ({ label: s, value: s }))
  }

  async function columnOptions(fileKeyword: string, sheetName: string) {
    const cols = await loadColumns(fileKeyword, sheetName)
    return cols.map((c) => ({ label: c, value: c }))
  }

  return {
    files,
    loadFiles,
    loadSheets,
    loadColumns,
    fileOptions,
    sheetOptions,
    columnOptions,
  }
}
