<script setup>
import { ref, computed } from 'vue'
import { api } from '../api/recorder'
import { gestationLabel, gestationalDays, sources } from './pregnancy'

const props = defineProps({ snapshot: { type: Object, required: true } })
const emit = defineEmits(['saved', 'close', 'failed'])
const current = props.snapshot.pregnancy
const date = ref(current?.edd_date || '')
const source = ref(current?.edd_source || 'manual')
const lmp = ref(current?.lmp_date || '')
const note = ref('')
const saving = ref(false)
const error = ref('')
const canCalculate = computed(() => source.value === 'lmp' && Boolean(lmp.value))
const days = computed(() => gestationalDays(date.value, props.snapshot.today))

function calculate() {
  const day = new Date(lmp.value + 'T00:00:00Z')
  day.setUTCDate(day.getUTCDate() + 280)
  date.value = day.toISOString().slice(0, 10)
}

async function save() {
  saving.value = true
  error.value = ''
  try {
    const snapshot = await api('/pregnancy', {
      method: 'PUT',
      data: { edd_date: date.value, edd_source: source.value, lmp_date: lmp.value || null, note: note.value },
    })
    emit('saved', snapshot)
  } catch (failure) {
    if (failure.status === 401) emit('failed', failure)
    else error.value = failure.message
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="page-heading">
    <h1>预产期设置</h1>
    <button class="button-text" type="button" @click="emit('close')">返回</button>
  </div>

  <form class="editor" @submit.prevent="save">
    <section class="panel fields" aria-label="预产期">
      <label class="field">
        <span>计算依据</span>
        <select v-model="source">
          <option v-for="(label, value) in sources" :key="value" :value="value">{{ label }}</option>
        </select>
      </label>
      <div class="field-row">
        <label class="field">
          <span>末次月经日期 <small>选填</small></span>
          <input v-model="lmp" type="date">
        </label>
        <label class="field">
          <span>预产期</span>
          <input v-model="date" type="date" required>
        </label>
      </div>
      <button v-if="canCalculate" class="button-secondary" type="button" @click="calculate">按末次月经加 280 天</button>
      <p v-if="days !== null" class="preview-line">{{ gestationLabel(days) }}</p>
      <label class="field">
        <span>设置说明 <small>选填</small></span>
        <textarea v-model="note" rows="2" maxlength="1000" placeholder="例如：采用这次超声报告上的日期"></textarea>
      </label>
    </section>
    <p v-if="error" class="form-message" role="alert">{{ error }}</p>
    <div class="editor-actions">
      <button class="button-primary" type="submit" :disabled="saving">{{ saving ? '正在保存…' : '保存预产期' }}</button>
    </div>
  </form>

  <section v-if="snapshot.history.length" class="panel history">
    <h2>设置历史</h2>
    <ol>
      <li v-for="(entry, index) in snapshot.history" :key="index">
        <div><strong>{{ entry.edd_date }}</strong><span>{{ sources[entry.source] || entry.source }}</span></div>
        <p v-if="entry.note">{{ entry.note }}</p>
        <time :datetime="entry.changed_at">{{ new Date(entry.changed_at).toLocaleString('zh-CN') }}</time>
      </li>
    </ol>
  </section>
</template>
