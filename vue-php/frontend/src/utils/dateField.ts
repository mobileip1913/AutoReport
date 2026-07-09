export const DATE_FIELD_WEEKDAYS = ['一', '二', '三', '四', '五', '六', '日']

export function parseIsoDate(str: string): Date | null {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(str || '').trim())
  if (!m) return null
  const d = new Date(+m[1], +m[2] - 1, +m[3])
  if (d.getFullYear() !== +m[1] || d.getMonth() !== +m[2] - 1 || d.getDate() !== +m[3]) return null
  return d
}

export function formatIsoDate(d: Date): string {
  const y = d.getFullYear()
  const mo = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${mo}-${day}`
}

export function formatDateDisplay(iso: string): string {
  const d = parseIsoDate(iso)
  if (!d) return '选择日期'
  const mo = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()} / ${mo} / ${day}`
}

export function calendarDays(year: number, month: number): Date[] {
  const first = new Date(year, month, 1)
  const startOffset = (first.getDay() + 6) % 7
  const start = new Date(year, month, 1 - startOffset)
  return Array.from(
    { length: 42 },
    (_, i) => new Date(start.getFullYear(), start.getMonth(), start.getDate() + i),
  )
}
