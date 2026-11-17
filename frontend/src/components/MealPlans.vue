<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api/recorder'
import { showTip } from '../tips'
import { mealLabels } from './meals'

const emit = defineEmits(['close', 'failed', 'use-meal'])
const data = ref(null)
const busy = ref(true)
const preference = ref({ month: null, days: {} })
const storageKey = 'preg.meal-plans'
const month = computed({
  get: () => preference.value.month ?? data.value?.recommended_month ?? '',
  set: value => {
    preference.value.month = value || null
    remember()
  },
})
const group = computed(() => data.value?.groups.find(item => item.month === month.value))
const menu = computed(() => {
  if (!group.value) return null
  const days = group.value.days
  return days.find(item => item.day === preference.value.days[month.value])
    ?? days[data.value.rotation_day % days.length]
})

function remember() {
  try {
    sessionStorage.setItem(storageKey, JSON.stringify({ today: data.value.today, ...preference.value }))
  } catch {}
}

async function load() {
  busy.value = true
  try {
    data.value = await api('/meal-plans')
    try {
      const saved = JSON.parse(sessionStorage.getItem(storageKey))
      if (saved?.today === data.value.today) {
        preference.value = { month: saved.month, days: { ...saved.days } }
      }
    } catch {}
  } catch (problem) {
    if (problem.status === 401) emit('failed', problem)
    else showTip(problem.message, 'error')
  } finally {
    busy.value = false
  }
}

function changeMenu() {
  const days = group.value.days
  const index = days.indexOf(menu.value)
  preference.value.days[month.value] = days[(index + 1) % days.length].day
  remember()
}

function useMeal(kind) {
  emit('use-meal', { date: data.value.today, kind, text: menu.value[kind].join('、') })
}

onMounted(load)
</script>

<template>
  <div class="page-heading">
    <h1>今日食谱</h1>
    <button class="button-text" type="button" @click="emit('close')">返回</button>
  </div>

  <p v-if="busy" role="status">正在读取食谱…</p>
  <button v-else-if="!data" class="button-secondary" type="button" @click="load">重试</button>

  <div v-else class="fields">
    <div class="panel fields">
      <div class="section-heading meal-plan-meta">
        <time :datetime="data.today">{{ data.today }}</time>
        <button class="button-text" type="button"
          @click="showTip('这是按孕周轮换的参考菜单。食材和做法请结合个人饮食要求选择。')">食谱说明</button>
      </div>
      <div class="meal-plan-controls">
        <label class="field">
          <span>参考食谱组</span>
          <select v-model="month">
            <option value="">{{ data.recommended_month ? '按孕周推荐' : '选择食谱组' }}</option>
            <option v-for="item in data.groups" :key="item.month" :value="item.month">孕{{ item.month }}月食谱组</option>
          </select>
        </label>
        <button v-if="menu" class="button-secondary" type="button" :disabled="group.days.length < 2" @click="changeMenu">换一套</button>
      </div>
    </div>

    <div v-if="menu" class="fields">
      <section v-for="(label, kind) in mealLabels" :key="kind" class="panel fields meal-plan-card">
        <h2>{{ label }}</h2>
        <ul :aria-label="label + '菜品'">
          <li v-for="(dish, index) in menu[kind]" :key="index">{{ dish }}</li>
        </ul>
        <button class="button-text" type="button" :aria-label="`带入${label}草稿`" @click="useMeal(kind)">带入草稿</button>
      </section>
    </div>
  </div>
</template>

<style scoped>
.meal-plan-meta { color: var(--color-text-secondary); font-size: 0.875rem; }

.meal-plan-controls {
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: end;
  gap: 0.75rem;
}

.meal-plan-controls button { min-block-size: 3rem; }

.meal-plan-card {
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: start;
  column-gap: 0.5rem;
  row-gap: 0.5rem;
}

.meal-plan-card ul {
  grid-column: 1 / -1;
  margin: 0;
  padding-inline-start: 1.25rem;
  color: var(--color-text-secondary);
  overflow-wrap: anywhere;
}

.meal-plan-card button {
  grid-column: 2;
  grid-row: 1;
  margin-block-start: -0.625rem;
  margin-inline-end: -0.625rem;
}
</style>
