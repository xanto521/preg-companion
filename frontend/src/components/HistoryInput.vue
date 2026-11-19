<script setup>
import { computed, nextTick, ref, useId } from 'vue'

const props = defineProps({
  label: { type: String, required: true },
  options: { type: Array, required: true },
  maxlength: { type: Number, required: true },
})
const value = defineModel({ type: String, default: '' })
const id = useId()
const listId = `${id}-options`
const open = ref(false)
const query = ref('')
const active = ref(-1)
const normalize = text => text.normalize('NFKC').toLowerCase().replace(/\s+/g, '')
const matches = computed(() => {
  const needle = normalize(query.value)
  if (!needle) return props.options.slice(0, 5)
  const chars = [...needle]
  const direct = []
  const similar = []
  for (const option of props.options) {
    const name = normalize(option)
    if (name.includes(needle)) {
      direct.push(option)
      continue
    }
    let index = 0
    for (const char of name) {
      if (char === chars[index]) index++
    }
    if (index === chars.length) similar.push(option)
  }
  return [...direct, ...similar].slice(0, 8)
})
const expanded = computed(() => open.value && matches.value.length > 0)

function showRecent() {
  if (open.value) return
  query.value = ''
  active.value = -1
  open.value = true
}

function update(event) {
  const typed = event.target.value
  query.value = typed
  value.value = typed
  active.value = -1
  open.value = true
}

function choose(option) {
  value.value = option
  open.value = false
  active.value = -1
}

async function navigate(event) {
  if (event.isComposing || event.keyCode === 229) return
  if (event.key === 'Escape' && open.value) {
    event.preventDefault()
    open.value = false
  }
  if (event.key === 'Enter' && expanded.value && active.value >= 0) {
    event.preventDefault()
    choose(matches.value[active.value])
  }
  if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return
  showRecent()
  if (!expanded.value) return
  event.preventDefault()
  const count = matches.value.length
  active.value = event.key === 'ArrowDown'
    ? (active.value + 1) % count
    : (active.value <= 0 ? count - 1 : active.value - 1)
  await nextTick()
  document.getElementById(`${listId}-${active.value}`)?.scrollIntoView({ block: 'nearest' })
}
</script>

<template>
  <div class="field history-input">
    <label :for="id">{{ label }}</label>
    <input :id="id" :value="value" :maxlength="maxlength" autocomplete="off" role="combobox"
      aria-autocomplete="list" :aria-expanded="expanded" :aria-controls="listId"
      :aria-activedescendant="expanded && active >= 0 ? `${listId}-${active}` : undefined"
      @focus="showRecent" @click="showRecent" @blur="open = false" @keydown="navigate"
      @input="!$event.isComposing && update($event)" @compositionend="update">
    <ul v-show="expanded" :id="listId" class="history-options" role="listbox" :aria-label="label + '历史选项'">
      <li v-if="!query.trim()" role="presentation" class="history-options-caption">最近使用</li>
      <li v-for="(option, index) in matches" :id="`${listId}-${index}`" :key="option" role="option"
        :aria-selected="active === index" @mousedown.prevent @click="choose(option)">{{ option }}</li>
    </ul>
  </div>
</template>
