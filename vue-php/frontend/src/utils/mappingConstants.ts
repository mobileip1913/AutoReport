export const AGG_OPTIONS = [
  { label: '求和 sum', value: 'sum' },
  { label: '计数 count', value: 'count' },
  { label: '去重计数', value: 'count_distinct' },
  { label: '去重求和', value: 'sum_dedup' },
  { label: '去重取最大', value: 'max_dedup' },
  { label: '平均值 avg', value: 'avg' },
]

export const MAPPING_TABS = [
  { key: 'fetch', label: '取数' },
  { key: 'reuse', label: '复用字段' },
  { key: 'per_order', label: '每单金额' },
  { key: 'ratio', label: '按比例' },
  { key: 'placeholder', label: '占位' },
] as const

export type MappingTab = (typeof MAPPING_TABS)[number]['key']

export const LINE_TYPE_BY_TAB: Record<MappingTab, string> = {
  fetch: 'fetch',
  reuse: 'fetch',
  per_order: 'per_order',
  ratio: 'ratio',
  placeholder: 'manual',
}

export interface MappingPart {
  ref_field_code?: string
  source_file_keyword?: string
  sheet_name?: string
  column_header?: string
  aggregation?: string
  combine_op?: string
  join_to_orders?: boolean
  join_keys?: string[]
  sources?: Array<{
    source_file_keyword?: string
    sheet_name?: string
    column_header?: string
    combine_op?: string
  }>
}

export function defaultSourcePart(): MappingPart {
  return {
    combine_op: 'add',
    aggregation: 'sum',
    source_file_keyword: '',
    sheet_name: '',
    column_header: '',
    join_to_orders: false,
    join_keys: ['Order ID'],
  }
}

export function defaultRefPart(): MappingPart {
  return { combine_op: 'add', ref_field_code: '' }
}

export function flatPartsFromApi(parts: MappingPart[]): MappingPart[] {
  if (!parts.length) return [defaultSourcePart()]
  return parts.map((p) => {
    if (p.ref_field_code) {
      return { combine_op: p.combine_op || 'add', ref_field_code: p.ref_field_code }
    }
    const src = p.sources?.[0]
    return {
      combine_op: p.combine_op || 'add',
      aggregation: p.aggregation || 'sum',
      source_file_keyword: p.source_file_keyword || src?.source_file_keyword || '',
      sheet_name: p.sheet_name || src?.sheet_name || '',
      column_header: p.column_header || src?.column_header || '',
      join_to_orders: !!p.join_to_orders,
      join_keys: p.join_keys?.length ? [...p.join_keys] : ['Order ID'],
    }
  })
}

export function partsToSaveBody(parts: MappingPart[], tab: MappingTab): MappingPart[] {
  if (tab === 'reuse') {
    return parts
      .filter((p) => p.ref_field_code)
      .map((p) => ({ combine_op: p.combine_op || 'add', ref_field_code: p.ref_field_code }))
  }
  return parts.map((p) => ({
    combine_op: p.combine_op || 'add',
    aggregation: p.aggregation || 'sum',
    source_file_keyword: p.source_file_keyword || undefined,
    sheet_name: p.sheet_name || '',
    column_header: p.column_header || '',
    join_to_orders: !!p.join_to_orders,
    join_keys: p.join_to_orders ? (p.join_keys || ['Order ID']).filter(Boolean) : [],
    sources: [
      {
        source_file_keyword: p.source_file_keyword,
        sheet_name: p.sheet_name || '',
        column_header: p.column_header || '',
        combine_op: 'add',
      },
    ],
  }))
}

export function detectTabFromMapping(data: Record<string, unknown>): MappingTab {
  const lineType = String(data.line_type || '').toLowerCase()
  const parts = (data.parts as MappingPart[]) || []
  if (lineType === 'per_order') return 'per_order'
  if (lineType === 'ratio') return 'ratio'
  if (lineType === 'manual') return 'placeholder'
  if (parts.length && parts.every((p) => p.ref_field_code)) return 'reuse'
  if (parts.length) return 'fetch'
  return 'placeholder'
}
