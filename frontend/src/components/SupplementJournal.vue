<script setup>
import { nextTick, ref, watch } from 'vue'
import { showTip, watchError } from '../tips'
import { api } from '../api/recorder'
import DayPicker from './DayPicker.vue'
import { displayTime } from './pregnancy'

const props = defineProps({ today: { type: String, required: true }, initialPlanId: Number })
const emit = defineEmits(['close', 'failed'])
const day = ref(props.today)
const plans = ref([])
const planList = ref(null)
const form = ref(null)
const busy = ref(false)
const error = ref('')
watchError(error)

function fail(problem) {
  if (problem.status === 401) emit('failed', problem)
  else error.value = problem.message
}

async function refresh() {
  plans.value = await api(`/supplements?day=${day.value}`)
}

async function load() {
  busy.value = true
  error.value = ''
  try {
    await refresh()
    if (day.value === props.today && props.initialPlanId) {
      await nextTick()
      planList.value?.querySelector('[data-highlight="true"]')?.scrollIntoView({ block: 'nearest' })
    }
  } catch (problem) {
    plans.value = []
    fail(problem)
  } finally { busy.value = false }
}
watch(day, load, { immediate: true })

function edit(plan = null) {
  error.value = ''
  form.value = {
    id: plan?.id,
    name: plan?.name || '',
    dosage: plan?.dosage || '',
    start_date: plan?.start_date || day.value,
    end_date: plan?.end_date || '',
    remind_time: displayTime(plan?.remind_time),
    active: plan?.active ?? true,
    viewer_visible: plan?.viewer_visible ?? false,
    version: plan?.version,
  }
}

async function save() {
  busy.value = true
  error.value = ''
  try {
    const { id, ...data } = form.value
    data.end_date ||= null
    data.remind_time ||= null
    await api(id ? `/supplements/${id}` : '/supplements', { method: id ? 'PUT' : 'POST', data })
    form.value = null
    showTip('已保存补剂计划。', 'success')
    await refresh()
  } catch (problem) { fail(problem) }
  finally { busy.value = false }
}

async function check(plan) {
  busy.value = true
  error.value = ''
  try {
    const taken = !plan.taken
    await api(`/supplements/${plan.id}/check`, { method: 'POST', data: { day: day.value, taken } })
    plan.taken = taken
    showTip(taken ? '已打卡。' : '已撤销打卡。', 'success')
  } catch (problem) { fail(problem) }
  finally { busy.value = false }
}
</script>

<template>
  <div class="page-heading">
    <h1>补剂打卡</h1>
    <button class="button-text" type="button" :disabled="busy" @click="emit('close')">返回</button>
  </div>
  <DayPicker v-model="day" :busy="busy || !!form" />
  <section class="panel fields">
    <div class="section-heading">
      <h2>补剂计划</h2>
      <button v-if="!form" class="button-primary" type="button" :disabled="busy" @click="edit()">添加计划</button>
    </div>
    <form v-if="form" class="fields milestone-editor" @submit.prevent="save">
      <div class="field-row">
        <label class="field"><span>补剂名称</span><input v-model="form.name" maxlength="100" required></label>
        <label class="field"><span>用量 <small>选填</small></span><input v-model="form.dosage" maxlength="150"></label>
        <label class="field"><span>开始日期</span><input v-model="form.start_date" type="date" required></label>
        <label class="field"><span>结束日期 <small>选填</small></span><input v-model="form.end_date" type="date" :min="form.start_date"></label>
      </div>
      <label class="field"><span>每天提醒时间</span><input v-model="form.remind_time" type="time" :required="form.viewer_visible"></label>
      <label class="check-field"><input v-model="form.viewer_visible" type="checkbox">同步提醒到订阅日历</label>
      <button class="button-text settings-action" type="button" @click="showTip('日历标题显示「补剂」。日历应用刷新订阅后会更新提醒。')">提醒说明</button>
      <label class="check-field"><input v-model="form.active" type="checkbox">启用此计划</label>
      <div class="settings-controls">
        <button class="button-secondary" type="button" :disabled="busy" @click="form = null">取消</button>
        <button class="button-primary" type="submit" :disabled="busy">保存计划</button>
      </div>
    </form>
    <button v-if="error && !form && !plans.length" class="button-text settings-action" :disabled="busy" type="button" @click="load">重新加载</button>
    <ul v-if="plans.length" ref="planList" class="settings-list">
      <li v-for="plan in plans" :key="plan.id" class="calendar-plan-target"
        :data-highlight="day === props.today && plan.id === props.initialPlanId">
        <div class="section-heading">
          <div>
            <strong>{{ plan.name }}</strong>
            <p class="settings-help">{{ plan.dosage }}{{ plan.dosage && plan.remind_time ? ' · ' : '' }}{{ plan.remind_time ? '每天 ' + displayTime(plan.remind_time) : '' }}</p>
          </div>
          <span class="entry-state" :data-done="plan.taken">{{ plan.taken ? '已打卡' : plan.scheduled ? '待打卡' : '当天无需打卡' }}</span>
        </div>
        <div class="settings-controls">
          <button v-if="plan.scheduled || plan.taken" class="button-secondary" type="button" :disabled="busy || !!form"
            @click="check(plan)">{{ plan.taken ? '撤销打卡' : '打卡' }}</button>
          <button class="button-text" type="button" :disabled="busy || !!form" @click="edit(plan)">编辑计划</button>
        </div>
      </li>
    </ul>
    <p v-else-if="!busy && !error" class="settings-help">还没有补剂计划。</p>
  </section>
</template>
