<script setup>
import { computed, ref } from 'vue'
import { api } from '../api/recorder'
import { showTip } from '../tips'
import HistoryInput from './HistoryInput.vue'
import ConfirmTip from './ConfirmTip.vue'
import { displayTime } from './pregnancy'

const props = defineProps({
  records: { type: Array, required: true },
  today: { type: String, required: true },
  hospitals: { type: Array, required: true },
  initialId: Number,
})
const emit = defineEmits(['close', 'changed', 'failed'])
const field = ref(null)
const busy = ref(false)
const confirming = ref(false)
const groups = computed(() => [
  { title: '即将到来', records: props.records.filter(record => record.day >= props.today) },
  { title: '过往预约', records: props.records.filter(record => record.day < props.today).reverse() },
])

function open(record) {
  field.value = record
    ? {
        id: record.id, version: record.version, day: record.day, time: displayTime(record.time),
        title: record.title || '', hospital: record.hospital || '', viewer_visible: record.viewer_visible,
      }
    : { day: props.today, time: '', hospital: '', title: '', viewer_visible: false }
}

if (props.initialId) {
  const record = props.records.find(item => item.id === props.initialId)
  if (record) open(record)
}

async function save() {
  busy.value = true
  try {
    const { id, ...data } = field.value
    data.time ||= null
    data.hospital = data.hospital?.trim() || null
    data.title = data.title?.trim() || null
    const record = await api(id ? `/appointments/${id}` : '/appointments', { method: id ? 'PUT' : 'POST', data })
    emit('changed', record)
    field.value = null
    showTip('已保存预约。', 'success')
  } catch (problem) {
    emit('failed', problem)
  } finally {
    busy.value = false
  }
}

async function remove() {
  busy.value = true
  try {
    const { id, version } = field.value
    await api(`/appointments/${id}?version=${version}`, { method: 'DELETE' })
    emit('changed', { id, removed: true })
    field.value = null
    showTip('已删除预约。', 'success')
  } catch (problem) {
    emit('failed', problem)
  } finally {
    busy.value = false
    confirming.value = false
  }
}
</script>

<template>
  <div class="page-heading">
    <h1>{{ field ? (field.id ? '编辑产检预约' : '新建产检预约') : '产检预约' }}</h1>
    <button class="button-text" type="button" :disabled="busy" @click="emit('close')">返回</button>
  </div>

  <form v-if="field" class="panel fields checkup-editor" @submit.prevent="save">
    <fieldset class="fields" :disabled="busy">
      <label class="field"><span>检查项目</span><input v-model="field.title" maxlength="150" placeholder="如：超声检查"></label>
      <div class="field-row">
        <label class="field"><span>预约日期</span><input v-model="field.day" type="date" required></label>
        <label class="field"><span>预约时间</span><input v-model="field.time" type="time"></label>
      </div>
      <HistoryInput v-model="field.hospital" label="预约医院" :maxlength="150" :options="hospitals" />
      <label class="check-field"><input v-model="field.viewer_visible" type="checkbox">同步到家人页和订阅日历</label>
    </fieldset>
    <div class="editor-actions">
      <button class="button-primary" type="submit" :disabled="busy">{{ busy ? '请稍候…' : '保存预约' }}</button>
      <button class="button-secondary" type="button" :disabled="busy" @click="field = null">返回预约列表</button>
      <button v-if="field.id" class="button-text" type="button" :disabled="busy" @click="confirming = true">删除预约</button>
    </div>
    <ConfirmTip v-if="confirming" message="确定删除这条预约？" action="删除预约" :busy="busy"
      @cancel="confirming = false" @confirm="remove" />
  </form>

  <template v-else>
    <button class="button-primary" type="button" @click="open()">新建预约</button>
    <section v-for="group in groups" :key="group.title" class="checkup-section">
      <h2>{{ group.title }}</h2>
      <p v-if="!group.records.length" class="panel empty-records">暂无预约。</p>
      <ul v-else class="record-list">
        <li v-for="record in group.records" :key="record.id">
          <button class="record-button panel" type="button" @click="open(record)">
            <span><strong>{{ record.title || '产检预约' }}</strong><small v-if="record.hospital">{{ record.hospital }}</small></span>
            <span class="record-age">{{ record.day }} {{ displayTime(record.time) || '全天' }}</span>
          </button>
        </li>
      </ul>
    </section>
  </template>
</template>
