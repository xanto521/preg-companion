<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api/recorder'
import MetricReference from './MetricReference.vue'
import MetricTrends from './MetricTrends.vue'

const emit = defineEmits(['close', 'failed'])
const metrics = ref(null)
const error = ref('')

async function load() {
  error.value = ''
  try {
    metrics.value = await api('/metrics/trends')
  } catch (problem) {
    if (problem.status === 401) emit('failed', problem)
    else error.value = problem.message
  }
}

function readSeries(code) {
  return api(`/metrics/${encodeURIComponent(code)}/series`)
}

onMounted(load)
</script>

<template>
  <div class="page-heading">
    <h1>趋势</h1>
    <button class="button-text" type="button" @click="emit('close')">返回</button>
  </div>
  <div v-if="error" class="panel fields">
    <p class="form-message" role="alert">{{ error }}</p>
    <button class="button-secondary" type="button" @click="load">重试</button>
  </div>
  <p v-else-if="!metrics" role="status">正在读取指标…</p>
  <MetricTrends v-else :metrics="metrics" :read-series="readSeries" @failed="emit('failed', $event)">
    <template #default="{ metric, updateMetric }">
      <MetricReference :key="metric.code" :metric="metric" @updated="updateMetric" @failed="emit('failed', $event)" />
    </template>
  </MetricTrends>
</template>
