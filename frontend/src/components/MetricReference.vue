<script setup>
import { ref } from 'vue'
import { showTip } from '../tips'
import { api } from '../api/recorder'

const props = defineProps({ metric: { type: Object, required: true } })
const emit = defineEmits(['updated', 'failed'])
const editing = ref(false)
const busy = ref(false)
const limits = ref(null)

function edit() {
  limits.value = { ref_low: props.metric.ref_low ?? '', ref_high: props.metric.ref_high ?? '' }
  editing.value = true
}

async function save() {
  busy.value = true
  try {
    const data = Object.fromEntries(Object.entries(limits.value).map(([key, value]) => [key, value === '' ? null : value]))
    const metric = await api(`/metrics/${encodeURIComponent(props.metric.code)}/reference`, { method: 'PUT', data })
    emit('updated', metric)
    editing.value = false
    showTip('已保存参考范围。', 'success')
  } catch (problem) {
    if (problem.status === 401) emit('failed', problem)
    else showTip(problem.message, 'error')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <button v-if="!editing" class="button-text settings-action" type="button" @click="edit">填写参考范围</button>
  <form v-else class="fields trend-reference" @submit.prevent="save">
    <button class="trend-retry" type="button" @click="showTip('按报告填写，留空表示该侧没有参考界限。')">填写说明</button>
    <div class="field-row">
      <label class="field"><span>参考下限</span><input v-model="limits.ref_low" type="number" step="any" :disabled="busy"></label>
      <label class="field"><span>参考上限</span><input v-model="limits.ref_high" type="number" step="any" :disabled="busy"></label>
    </div>
    <div class="settings-controls">
      <button class="button-secondary" type="button" :disabled="busy" @click="editing = false">取消</button>
      <button class="button-primary" type="submit" :disabled="busy">保存参考范围</button>
    </div>
  </form>
</template>
