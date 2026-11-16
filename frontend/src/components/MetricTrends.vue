<script setup>
import { ref, watch } from 'vue'
import TrendChart from './TrendChart.vue'

const props = defineProps({
  metrics: { type: Array, required: true },
  readSeries: { type: Function, required: true },
})
const emit = defineEmits(['failed'])
const code = ref('')
const axis = ref('gestation')
const series = ref(null)
const busy = ref(false)
const error = ref('')
let generation = 0

watch(() => props.metrics, metrics => {
  if (!metrics.some(metric => metric.code === code.value)) {
    code.value = (metrics.find(metric => metric.code === 'weight') || metrics[0])?.code || ''
  }
}, { immediate: true })
watch(code, load, { immediate: true })

function fail(problem) {
  if (problem.status === 401 || problem.status === 404) emit('failed', problem)
  error.value = problem.message
}

async function load() {
  const request = ++generation
  series.value = null
  error.value = ''
  if (!code.value) {
    busy.value = false
    return
  }
  busy.value = true
  try {
    const result = await props.readSeries(code.value)
    if (request === generation) series.value = result
  } catch (problem) {
    if (request === generation) fail(problem)
  } finally {
    if (request === generation) busy.value = false
  }
}

function updateMetric(metric) {
  if (series.value?.metric.code === metric.code) {
    series.value = { ...series.value, metric }
  }
}
</script>

<template>
  <section class="trend-panel" aria-labelledby="trends-heading">
    <h2 id="trends-heading">指标趋势</h2>
    <template v-if="metrics.length">
      <div class="trend-options" aria-label="指标">
        <button v-for="metric in metrics" :key="metric.code" type="button" :aria-pressed="code === metric.code"
          @click="code = metric.code">{{ metric.name }}</button>
      </div>
      <div class="trend-tools">
        <div class="trend-options" aria-label="横轴">
          <button type="button" :aria-pressed="axis === 'gestation'" @click="axis = 'gestation'">按孕周</button>
          <button type="button" :aria-pressed="axis === 'date'" @click="axis = 'date'">按日期</button>
        </div>
      </div>
      <slot v-if="series" :metric="series.metric" :updateMetric="updateMetric" />
      <p v-if="error" class="trend-attention" role="alert">{{ error }}</p>
      <button v-if="error && !series" class="trend-retry" type="button" @click="load">重试</button>
      <p v-if="busy && !series" class="trend-hint" role="status">正在读取指标…</p>
      <TrendChart v-if="series" :series="series" :axis="axis" />
    </template>
    <p v-else class="trend-hint">还没有可查看的指标。</p>
  </section>
</template>
