<script setup>
import { nextTick, onMounted, ref } from 'vue'
import { showTip, watchError } from '../tips'
import { api } from '../api/recorder'
import ShareLinks from './ShareLinks.vue'

const props = defineProps({ initialRuleId: Number })
const emit = defineEmits(['close', 'failed'])
const rules = ref([])
const form = ref(null)
const titleField = ref(null)
const busy = ref(true)
const error = ref('')
watchError(error)
const presets = ['建档', 'NT', '唐筛或无创', '大排畸', '糖耐量', 'B 族链球菌筛查', '胎心监护']

function weekLabel(days) {
  return `${Math.floor(days / 7)} 周 ${days % 7} 天`
}

function fail(problem) {
  if (problem.status === 401) emit('failed', problem)
  else error.value = problem.message
}

async function edit(rule = null) {
  error.value = ''
  form.value = {
    id: rule?.id,
    version: rule?.version,
    title: rule?.title || '',
    startWeek: rule ? Math.floor(rule.start_ga_days / 7) : '',
    startDay: rule ? rule.start_ga_days % 7 : 0,
    endWeek: rule ? Math.floor(rule.end_ga_days / 7) : '',
    endDay: rule ? rule.end_ga_days % 7 : 0,
    enabled: rule?.enabled ?? true,
    note: rule?.note || '',
  }
  await nextTick()
  titleField.value?.focus()
}

async function load() {
  busy.value = true
  error.value = ''
  try {
    rules.value = await api('/milestones')
  } catch (problem) {
    fail(problem)
  } finally {
    busy.value = false
  }
}

async function save() {
  const { startWeek, startDay, endWeek, endDay, ...values } = form.value
  busy.value = true
  error.value = ''
  try {
    const updated = await api('/milestones', {
      method: 'PUT',
      data: { ...values, start_ga_days: startWeek * 7 + startDay, end_ga_days: endWeek * 7 + endDay },
    })
    rules.value = [...rules.value.filter(rule => rule.id !== updated.id), updated]
      .sort((a, b) => a.start_ga_days - b.start_ga_days || a.end_ga_days - b.end_ga_days || a.id - b.id)
    form.value = null
    showTip('已保存里程碑规则。', 'success')
  } catch (problem) {
    fail(problem)
  } finally {
    busy.value = false
  }
}

onMounted(async () => {
  await load()
  const target = rules.value.find(rule => rule.id === props.initialRuleId)
  if (target) await edit(target)
})
</script>

<template>
  <div class="page-heading">
    <h1>里程碑与日历</h1>
    <button class="button-text" type="button" @click="emit('close')">返回</button>
  </div>

  <div class="fields">
    <section class="panel fields" aria-labelledby="milestones-heading">
      <div class="section-heading">
        <h2 id="milestones-heading">里程碑规则</h2>
        <button v-if="!form" class="button-secondary" type="button" :disabled="busy" @click="edit()">添加规则</button>
      </div>
      <button class="button-text settings-action" type="button" @click="showTip('日期随预产期重新计算，实际产检以医院安排为准。')">规则说明</button>

      <form v-if="form" class="fields milestone-editor" @submit.prevent="save">
        <label class="field">
          <span>项目名称</span>
          <input ref="titleField" v-model="form.title" maxlength="100" required>
        </label>
        <div v-if="!form.id" class="settings-controls milestone-presets">
          <button v-for="preset in presets" :key="preset" class="button-text" type="button" @click="form.title = preset">{{ preset }}</button>
        </div>
        <div class="field-row">
          <fieldset class="gestation-range">
            <legend>开始孕周</legend>
            <label class="field"><span>周数</span><input v-model.number="form.startWeek" type="number" inputmode="numeric" min="0" max="52" required></label>
            <label class="field"><span>加天数</span><input v-model.number="form.startDay" type="number" inputmode="numeric" min="0" max="6" required></label>
          </fieldset>
          <fieldset class="gestation-range">
            <legend>结束孕周</legend>
            <label class="field"><span>周数</span><input v-model.number="form.endWeek" type="number" inputmode="numeric" min="0" max="52" required></label>
            <label class="field"><span>加天数</span><input v-model.number="form.endDay" type="number" inputmode="numeric" min="0" max="6" required></label>
          </fieldset>
        </div>
        <label class="field"><span>备注 <small>选填</small></span><textarea v-model="form.note" maxlength="1000" rows="2"></textarea></label>
        <label class="check-field"><input v-model="form.enabled" type="checkbox">启用此规则并纳入日历</label>
        <div class="settings-controls">
          <button class="button-secondary" type="button" :disabled="busy" @click="form = null; error = ''">取消</button>
          <button class="button-primary" type="submit" :disabled="busy">保存规则</button>
        </div>
      </form>
      <button v-if="error && !form" class="button-text settings-action" type="button" :disabled="busy" @click="load">重新加载</button>

      <ul v-if="rules.length" class="settings-list">
        <li v-for="rule in rules" :key="rule.id">
          <div class="section-heading">
            <div>
              <strong>{{ rule.title }}</strong>
              <p class="settings-help">{{ weekLabel(rule.start_ga_days) }} 至 {{ weekLabel(rule.end_ga_days) }} · {{ rule.enabled ? '已启用' : '已停用' }}</p>
            </div>
            <button class="button-text" type="button" :disabled="busy" @click="edit(rule)">编辑</button>
          </div>
          <p v-if="rule.starts_on">{{ rule.starts_on === rule.ends_on ? rule.starts_on : `${rule.starts_on} 至 ${rule.ends_on}` }}</p>
          <p v-else class="settings-help">日期待设置</p>
          <p v-if="rule.note" class="settings-help">{{ rule.note }}</p>
        </li>
      </ul>
      <p v-else-if="!busy && !form && !error" class="settings-help">还没有里程碑规则。</p>
    </section>

    <ShareLinks @failed="emit('failed', $event)" />
  </div>
</template>
