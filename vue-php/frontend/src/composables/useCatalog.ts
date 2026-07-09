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
    files.value = data.files ?? data.tree?.files ?? []
  }

  async function loadSheets(fileKeyword: string) {
    const id = dataSourceId()
    if (!id || !fileKeyword) return []
    if (sheetsByFile.value[fileKeyword]) return sheetsByFile.value[fileKeyword]
    const { data } = await api.get(`/api/data-sources/${id}/schema`, {
      params: { file_keyword: fileKeyword },
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
      params: { file_keyword: fileKeyword, sheet_name: sheetName },
    })
    const cols = (data.columns ?? []) as string[]
    columnsByKey.value[key] = cols
    return cols
  }

  return { files, sheetsByFile, columnsByKey, loadFiles, loadSheets, loadColumns }
}
