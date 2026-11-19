<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { watchError } from '../tips'
import { api } from '../api/recorder'
import { displayTime } from './pregnancy'

const props = defineProps({ today: { type: String, required: true } })
const day = defineModel('day', { type: String, required: true })
const filter = defineModel('filter', { type: String, required: true })
const emit = defineEmits(['close', 'open', 'failed'])

const categories = {
  all: '全部', meal: '饮食', checkup: '产检', supplement: '补剂', symptom: '症状', note: '备注', milestone: '节点',
}
const states = { recorded: '记录', completed: '已完成', appointment: '预约', taken: '已打卡', pending: '待打卡', planned: '计划', window: '参考窗口' }
const week = ['一', '二', '三', '四', '五', '六', '日']
const monthKey = computed(() => day.value.slice(0, 7))
const year = computed(() => Number(monthKey.value.slice(0, 4)))
const month = computed(() => Number(monthKey.value.slice(5)))
const monthTitle = computed(() => `${year.value} 年 ${month.value} 月`)
const dayTitle = computed(() => {
  const selected = new Date(day.value + 'T00:00:00Z')
  return `${month.value} 月 ${selected.getUTCDate()} 日 · 周${week[(selected.getUTCDay() + 6) % 7]}`
})
const events = ref([])
const busy = ref(false)
const error = ref('')
watchError(error)
const dates = ref(null)
let requestNumber = 0

const daysInMonth = computed(() => {
  const first = new Date(monthKey.value + '-01T00:00:00Z')
  const offset = (first.getUTCDay() + 6) % 7
  const dates = Array.from({ length: offset }, () => null)
  const next = new Date(first)
  next.setUTCMonth(next.getUTCMonth() + 1, 0)
  for (let index = 1; index <= next.getUTCDate(); index++) {
    dates.push(`${monthKey.value}-${String(index).padStart(2, '0')}`)
  }
  return dates
})

const entriesByDay = computed(() => {
  const items = Object.fromEntries(daysInMonth.value.filter(Boolean).map(date => [date, []]))
  for (const entry of events.value) {
    if (filter.value !== 'all' && filter.value !== entry.kind) continue
    for (const date of Object.keys(items)) {
      if (date >= entry.start && date <= (entry.end || entry.start)) items[date].push(entry)
    }
  }
  return items
})

const selectedEntries = computed(() => [...(entriesByDay.value[day.value] || [])].sort((a, b) =>
  Number(b.state === 'appointment') - Number(a.state === 'appointment') ||
  (a.at || '').localeCompare(b.at || '') || a.title.localeCompare(b.title, 'zh-CN'),
))

const actions = { daily: '打开每日记录', symptoms: '打开症状记录', checkup: '打开产检记录', appointments: '打开产检预约',
  supplements: '打开补剂打卡', notes: '打开备注', milestones: '打开里程碑规则', pregnancy: '打开预产期设置' }
const emptyAction = computed(() => {
  if (filter.value === 'symptom') return { target: 'symptoms', label: '记当天症状' }
  if (filter.value === 'note') return { target: 'notes', label: '写当天备注' }
  if (filter.value === 'supplement') return { target: 'supplements', label: '查看补剂计划' }
  if (filter.value === 'all' || filter.value === 'meal') return { target: 'daily', label: '记当天饮食' }
  return null
})

function markers(date) {
  const entries = entriesByDay.value[date] || []
  const types = [...new Set(entries.filter(entry => entry.state !== 'window').map(entry => entry.kind))]
  return { types, span: entries.some(entry => entry.state === 'window') }
}

function describeDate(date) {
  const marker = markers(date)
  const names = marker.types.map(kind => categories[kind])
  if (marker.span) names.push('参考窗口')
  return names.length ? `${date} ${names.join('、')}` : date
}

async function load() {
  const current = ++requestNumber
  events.value = []
  busy.value = true
  error.value = ''
  try {
    const response = await api(`/journal-calendar?year=${year.value}&month=${month.value}`)
    if (current === requestNumber) events.value = response
  } catch (problem) {
    if (current === requestNumber) {
      if (problem.status === 401) emit('failed', problem)
      else error.value = problem.message
    }
  } finally {
    if (current === requestNumber) busy.value = false
  }
}

function move(amount) {
  const target = new Date(monthKey.value + '-01T00:00:00Z')
  target.setUTCMonth(target.getUTCMonth() + amount)
  day.value = target.toISOString().slice(0, 10)
}

async function selectDate(date) {
  day.value = date
  await nextTick()
  dates.value?.querySelector('[aria-pressed="true"]')?.focus({ preventScroll: true })
}

watch(monthKey, load, { immediate: true })
</script>

<template>
  <div class="page-heading">
    <h1>日历</h1>
    <div class="settings-controls">
      <button type="button" class="button-secondary" @click="day = props.today">今天</button>
      <button type="button" class="button-text" @click="emit('close')">返回</button>
    </div>
  </div>

  <div class="calendar-filters" role="group" aria-label="记录类型">
    <button v-for="(label, kind) in categories" :key="kind" type="button" class="button-text"
      :aria-pressed="filter === kind" @click="filter = kind">
      <i v-if="kind !== 'all'" class="calendar-mark" :data-kind="kind" aria-hidden="true"></i>{{ label }}
    </button>
  </div>

  <div class="journal-calendar">
    <section class="panel calendar-month" aria-label="月历">
      <div class="section-heading">
        <button class="button-secondary" type="button" aria-label="上个月" :disabled="year === 2 && month === 1" @click="move(-1)">‹</button>
        <h2 aria-live="polite">{{ monthTitle }}</h2>
        <button class="button-secondary" type="button" aria-label="下个月" :disabled="year === 9998 && month === 12" @click="move(1)">›</button>
      </div>
      <div class="calendar-grid calendar-week" aria-hidden="true">
        <span v-for="weekday in week" :key="weekday">{{ weekday }}</span>
      </div>
      <div ref="dates" class="calendar-grid" role="group" aria-label="选择日期">
        <template v-for="(date, index) in daysInMonth" :key="date || index">
          <span v-if="!date" aria-hidden="true"></span>
          <button v-else type="button" class="calendar-date" :aria-pressed="date === day" :aria-label="describeDate(date)"
            :aria-current="date === props.today ? 'date' : undefined" @click="selectDate(date)">
            <span>{{ Number(date.slice(-2)) }}</span>
            <span class="calendar-markers" aria-hidden="true">
              <i v-for="kind in markers(date).types.slice(0, 3)" :key="kind" class="calendar-mark" :data-kind="kind"></i>
              <span v-if="markers(date).types.length > 3" class="calendar-more">+</span>
            </span>
            <span v-if="markers(date).span" class="calendar-window" aria-hidden="true"></span>
          </button>
        </template>
      </div>
    </section>

    <section class="panel fields calendar-day" aria-labelledby="journal-calendar-day">
      <h2 id="journal-calendar-day">{{ dayTitle }}</h2>
      <button v-if="error" type="button" class="button-secondary" @click="load">重试</button>
      <p v-else-if="busy" role="status">正在读取日历…</p>
      <ul v-else-if="selectedEntries.length" class="calendar-entries">
        <li v-for="entry in selectedEntries" :key="entry.key">
          <button type="button" class="calendar-entry" :aria-label="`${actions[entry.target]}，${entry.title}`"
            @click="emit('open', entry, day)">
            <span class="calendar-entry-label">
              <i class="calendar-mark" :data-kind="entry.kind" aria-hidden="true"></i>
              {{ categories[entry.kind] }} · {{ states[entry.state] }}
            </span>
            <strong>{{ entry.at ? displayTime(entry.at) + ' · ' : '' }}{{ entry.title }}</strong>
            <small v-if="entry.end">{{ entry.start }} 至 {{ entry.end }}</small>
            <small v-if="entry.detail">{{ entry.detail }}</small>
          </button>
        </li>
      </ul>
      <template v-else>
        <p class="settings-help">{{ filter === 'all' ? '当天没有记录或日程。' : `当天没有${categories[filter]}记录。` }}</p>
        <button v-if="emptyAction" type="button" class="button-secondary"
          @click="emit('open', emptyAction, day)">{{ emptyAction.label }}</button>
      </template>
    </section>
  </div>
</template>
