export const FIELD_TYPE_LABELS: Record<string, string> = {
  compute: '计算',
  formula: '公式',
  review: '刷单',
  sample: '样品',
  placeholder: '占位',
  per_order: '每单',
  ratio: '比例',
  fetch: '取数',
  aux: '基础',
}

export function fieldTypeLabel(type: string): string {
  return FIELD_TYPE_LABELS[type] ?? type
}

export function fieldTypeClass(type: string): string {
  return `field-type-tag field-type-tag--${type}`
}
