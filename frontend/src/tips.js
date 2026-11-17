import { shallowRef, watch } from 'vue'

export const activeTip = shallowRef(null)
let timer

export function dismissTip() {
  clearTimeout(timer)
  activeTip.value = null
}

export function showTip(message, kind = 'info') {
  if (!message) return
  clearTimeout(timer)
  activeTip.value = { message, kind }
  timer = setTimeout(dismissTip, kind === 'success' ? 4000 : 8000)
}

export function watchError(error) {
  watch(error, message => showTip(message, 'error'))
}

export function showValidationTip(event) {
  event.preventDefault()
  const field = event.target
  if (field.form?.querySelector('input:invalid, select:invalid, textarea:invalid') !== field) return

  const label = field.labels?.[0]?.querySelector('span')?.textContent.trim()
  let message = field.validationMessage
  if (field.validity.valueMissing) message = label ? `请填写「${label}」。` : '请填写必填项。'
  if (field.validity.tooShort) message = `请至少输入 ${field.minLength} 个字符。`
  field.focus()
  showTip(message || '请检查填写的内容。', 'error')
}
