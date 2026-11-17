<script setup>
import AppBrand from '../components/AppBrand.vue'
import TipHost from '../components/TipHost.vue'
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { watchError } from '../tips'
import MetricTrends from '../components/MetricTrends.vue'
import { displayTime, gestationLabel } from '../components/pregnancy'

const token = window.location.pathname.match(/^\/view\/([A-Za-z0-9_-]{43})$/)?.[1]
const summary = ref(null)
const busy = ref(false)
const error = ref('')
watchError(error)
const unavailable = ref(false)
const titles = { checkup: '产检', daily: '每日记录', note: '备注' }
const meals = { breakfast: '早餐', lunch: '午餐', dinner: '晚餐', snack: '加餐' }
let generation = 0
let access = null
let connected = false
const countdown = computed(() => {
  const days = summary.value?.pregnancy?.days_until_due
  if (days === 0) return '今天是预产期'
  return days > 0 ? `距预产期还有 ${days} 天` : `已过预产期 ${-days} 天`
})

async function read(path) {
  if (!token) throw Object.assign(new Error('分享链接已失效或不存在。'), { status: 404 })
  const response = await fetch(`/api/view/${token}${path}`, {
    cache: 'no-store',
    credentials: 'omit',
    referrerPolicy: 'no-referrer',
  })
  if (!response.ok) {
    const message = response.status === 404 ? '分享链接或记录暂时不可用。' : '暂时无法加载，请重试。'
    throw Object.assign(new Error(message), { status: response.status })
  }
  return response.json()
}

function readSeries(code) {
  return read(`/metrics/${encodeURIComponent(code)}/series`)
}

function invalidate() {
  generation++
  connected = false
  access?.close()
  access = null
  summary.value = null
  busy.value = false
  unavailable.value = true
  error.value = '请向家人索取新的查看链接。'
}

async function load() {
  const request = ++generation
  busy.value = true
  summary.value = null
  unavailable.value = false
  error.value = ''
  try {
    const data = await read('/summary')
    if (request === generation) summary.value = data
  } catch (problem) {
    if (request === generation) {
      if (problem.status === 404) invalidate()
      else error.value = '暂时无法加载，请检查网络后重试。'
    }
  } finally {
    if (request === generation) busy.value = false
  }
}

function monitorAccess() {
  if (!token) {
    invalidate()
    return
  }
  access?.close()
  generation++
  connected = false
  summary.value = null
  busy.value = true
  unavailable.value = false
  error.value = ''
  const source = new EventSource(`/api/view/${token}/access`)
  access = source
  source.addEventListener('ready', () => {
    if (source !== access) return
    connected = true
    load()
  })
  source.addEventListener('unavailable', () => {
    if (source === access) invalidate()
  })
  source.onerror = async () => {
    if (source !== access) return
    const request = ++generation
    connected = false
    summary.value = null
    busy.value = false
    error.value = '暂时无法确认链接权限，请检查网络后重试。'
    if (source.readyState === EventSource.CLOSED) {
      try {
        await read('/summary')
      } catch (problem) {
        if (request === generation && problem.status === 404) invalidate()
      }
    }
  }
}

function recheck(problem) {
  if (connected && problem.status === 404 && !busy.value) load()
}

function retry() {
  if (connected) load()
  else monitorAccess()
}

function onPageShow(event) {
  if (event.persisted && !unavailable.value) retry()
}

function onVisibility() {
  if (!document.hidden && connected && !busy.value) load()
}

onMounted(() => {
  monitorAccess()
  window.addEventListener('pageshow', onPageShow)
  document.addEventListener('visibilitychange', onVisibility)
})
onUnmounted(() => {
  generation++
  access?.close()
  window.removeEventListener('pageshow', onPageShow)
  document.removeEventListener('visibilitychange', onVisibility)
})
</script>

<template>
  <main class="family-shell">
    <header class="family-heading">
      <AppBrand />
      <h1>{{ unavailable ? '分享链接不可用' : '家人查看' }}</h1>
    </header>
    <p v-if="busy" class="family-panel" role="status">正在读取分享内容…</p>
    <button v-else-if="error && !unavailable" class="trend-retry" type="button" @click="retry">重试</button>
    <template v-else-if="summary">
      <section v-if="summary.pregnancy" class="family-panel family-gestation">
        <h2>当前孕周</h2>
        <p class="family-week">{{ gestationLabel(summary.pregnancy.ga_days) }}</p>
        <p>{{ countdown }}</p>
        <p class="family-secondary">预产期 {{ summary.pregnancy.due_date }}</p>
      </section>

      <section v-if="summary.next_appointment" class="family-panel family-next">
        <h2>下次产检</h2>
        <p><strong>{{ summary.next_appointment.day }} {{ displayTime(summary.next_appointment.time) }}</strong></p>
      </section>

      <section v-if="summary.last_checkup" class="family-panel">
        <h2>最近一次产检</h2>
        <p class="family-secondary">{{ summary.last_checkup.day }} · {{ gestationLabel(summary.last_checkup.ga_days) }}</p>
        <p v-if="summary.last_checkup.text" class="family-entry-text">{{ summary.last_checkup.text }}</p>
      </section>

      <MetricTrends v-if="summary.metrics.length" :metrics="summary.metrics" :read-series="readSeries" @failed="recheck" />

      <section class="family-panel">
        <h2>共享记录</h2>
        <p v-if="!summary.entries.length" class="family-secondary">家人还没有分享记录。</p>
        <ol v-else class="family-timeline">
          <li v-for="(entry, index) in summary.entries" :key="index">
            <div class="family-entry-heading">
              <strong>{{ entry.title || titles[entry.kind] }}</strong>
              <time :datetime="entry.day">{{ entry.day }}</time>
            </div>
            <p v-if="entry.text" class="family-entry-text">{{ entry.text }}</p>
            <p v-if="entry.mood" class="family-secondary">心情：{{ entry.mood }}</p>
            <dl v-if="Object.keys(entry.meals).length" class="family-meals">
              <template v-for="(text, kind) in entry.meals" :key="kind">
                <dt>{{ meals[kind] || kind }}</dt><dd>{{ text }}</dd>
              </template>
            </dl>
            <ul v-if="entry.tags.length" class="family-tags">
              <li v-for="(tag, tagIndex) in entry.tags" :key="tagIndex">{{ tag }}</li>
            </ul>
          </li>
        </ol>
      </section>
      <footer class="family-footer">由家人记录</footer>
    </template>
  </main>
  <TipHost />
</template>
