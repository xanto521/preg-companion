export const sources = {
  manual: '手动填写',
  lmp: '按末次月经',
  ultrasound: '按超声校正',
}

export function gestationLabel(days) {
  if (days == null) return '孕周未记录'
  if (days < 0) return '早于孕周起算日'
  return `孕 ${Math.floor(days / 7)} 周 ${days % 7} 天`
}

export function gestationalDays(due, date) {
  if (!due || !date) return null
  return 280 - Math.round((Date.parse(due) - Date.parse(date)) / 86400000)
}

export function displayTime(value) {
  return value?.slice(0, 5) || ''
}
