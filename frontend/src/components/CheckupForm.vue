<script setup>
import { computed, ref, watch } from 'vue'
import { api } from '../api/recorder'
import { displayTime, gestationLabel, gestationalDays } from './pregnancy'

const props = defineProps({
  record: { type: Object, default: null },
  snapshot: { type: Object, required: true },
  options: { type: Array, required: true },
  previous: { type: Object, default: null },
})
const emit = defineEmits(['saved', 'close', 'failed'])
const saved = ref(props.record)
const draftKey = 'preg.checkup.' + (props.record?.id || 'new')
const field = ref({
  visit_date: props.record?.visit_date || props.snapshot.today,
  visit_time: displayTime(props.record?.visit_time),
  hospital: props.record ? props.record.hospital || '' : props.previous?.hospital || '',
  doctor: props.record ? props.record.doctor || '' : props.previous?.doctor || '',
  summary: props.record?.summary || '',
  advice: props.record?.advice || '',
  next_visit_date: props.record?.next_visit_date || '',
  next_visit_time: displayTime(props.record?.next_visit_time),
  viewer_visible: props.record?.viewer_visible ?? true,
  viewer_note: props.record?.viewer_note || '',
  metrics: { ...props.record?.metrics },
})
const commonCodes = ['weight', 'systolic_bp', 'diastolic_bp', 'fetal_heart_rate']
const rankedOptions = [...props.options].sort((a, b) => {
  const rank = code => commonCodes.includes(code) ? commonCodes.indexOf(code) : commonCodes.length
  return rank(a.code) - rank(b.code)
})
const queued = ref([])
const saving = ref(false)
const deleting = ref(false)
const error = ref('')
const restored = ref(false)
const kind = ref('report')
const attachmentKinds = { report: '报告', ultrasound: '超声图', other: '其他' }

try {
  const draft = JSON.parse(sessionStorage.getItem(draftKey))
  if (draft?.version === (props.record?.version ?? null) && draft.field) {
    Object.assign(field.value, draft.field)
    restored.value = true
  }
} catch {}

const showExtra = ref(rankedOptions.some(option => !commonCodes.includes(option.code) && field.value.metrics[option.code] != null))
const visibleOptions = computed(() => showExtra.value ? rankedOptions : rankedOptions.filter(option => commonCodes.includes(option.code)))

watch(field, value => {
  if (saving.value) return
  try {
    sessionStorage.setItem(draftKey, JSON.stringify({ version: saved.value?.version ?? null, field: value }))
  } catch {}
}, { deep: true })

const days = computed(() => {
  if (saved.value && field.value.visit_date === saved.value.visit_date && saved.value.ga_days != null) {
    return saved.value.ga_days
  }
  return gestationalDays(props.snapshot.pregnancy.edd_date, field.value.visit_date)
})

function chooseFiles(event) {
  error.value = ''
  for (const file of Array.from(event.target.files)) {
    if (file.size > 20 * 1024 * 1024) {
      error.value = '每个附件最多 20 MB。'
      continue
    }
    queued.value.push({ file, kind: kind.value })
  }
  event.target.value = ''
}

function clearDraft() {
  try { sessionStorage.removeItem(draftKey) } catch {}
}

async function save() {
  saving.value = true
  error.value = ''
  try {
    const data = { ...field.value }
    for (const key of ['visit_time', 'next_visit_date', 'next_visit_time']) data[key] ||= null
    data.metrics = Object.fromEntries(Object.entries(data.metrics).filter(([, value]) => value !== '' && value != null))
    const id = saved.value?.id
    if (id) data.version = saved.value.version
    saved.value = await api(id ? `/checkups/${id}` : '/checkups', {
      method: id ? 'PUT' : 'POST',
      data,
    })
    clearDraft()
    while (queued.value.length) {
      const item = queued.value[0]
      const data = new FormData()
      data.append('kind', item.kind)
      data.append('file', item.file)
      try {
        const attachment = await api(`/checkups/${saved.value.id}/attachments`, { method: 'POST', data })
        if (!saved.value.attachments.some(entry => entry.id === attachment.id)) saved.value.attachments.push(attachment)
        queued.value.shift()
      } catch (failure) {
        if (failure.status === 401) throw failure
        error.value = `记录已保存，附件「${item.file.name}」未上传。${failure.message}`
        return
      }
    }
    emit('saved', '已保存产检记录')
  } catch (failure) {
    if (failure.status === 401) emit('failed', failure)
    else error.value = failure.message
  } finally {
    saving.value = false
  }
}

async function remove() {
  saving.value = true
  error.value = ''
  try {
    await api(`/checkups/${saved.value.id}?version=${saved.value.version}`, { method: 'DELETE' })
    clearDraft()
    emit('saved', '已删除产检记录')
  } catch (failure) {
    deleting.value = false
    if (failure.status === 401) emit('failed', failure)
    else error.value = failure.message
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <div class="page-heading">
    <h1>{{ record ? '编辑产检' : '录入产检' }}</h1>
    <button class="button-text" type="button" :disabled="saving" @click="emit('close')">返回</button>
  </div>
  <p v-if="restored" class="preview-line" role="status">已恢复此标签页的草稿</p>

  <form class="editor checkup-editor" @submit.prevent="save">
    <fieldset :disabled="saving">
      <section class="panel fields">
        <h2>基本信息</h2>
        <div class="field-row">
          <label class="field"><span>就诊日期</span><input v-model="field.visit_date" type="date" required></label>
          <label class="field"><span>就诊时间 <small>选填</small></span><input v-model="field.visit_time" type="time"></label>
        </div>
        <p v-if="days !== null" class="preview-line">{{ gestationLabel(days) }}</p>
        <div class="field-row">
          <label class="field"><span>医院</span><input v-model="field.hospital" maxlength="150"></label>
          <label class="field"><span>医生</span><input v-model="field.doctor" maxlength="100"></label>
        </div>
      </section>

      <section v-if="rankedOptions.length" class="panel fields">
        <div class="section-heading">
          <h2>指标</h2>
          <button v-if="rankedOptions.length > commonCodes.length" class="button-text" type="button"
            :aria-expanded="showExtra" @click="showExtra = !showExtra">{{ showExtra ? '收起指标' : '更多指标' }}</button>
        </div>
        <div class="field-row">
          <label v-for="option in visibleOptions" :key="option.code" class="field">
            <span>{{ option.name }}</span>
            <span class="unit-input">
              <input v-model="field.metrics[option.code]" type="number" inputmode="decimal" step="any">
              <span>{{ option.unit }}</span>
            </span>
          </label>
        </div>
      </section>

      <section class="panel fields">
        <h2>报告与影像</h2>
        <div class="field-row">
          <label class="field">
            <span>附件类型</span>
            <select v-model="kind">
              <option v-for="(label, value) in attachmentKinds" :key="value" :value="value">{{ label }}</option>
            </select>
          </label>
          <label class="field">
            <span>添加文件 <small>每个最多 20 MB</small></span>
            <input type="file" accept="image/jpeg,image/png,image/webp,application/pdf,.jpg,.jpeg,.png,.webp,.pdf" multiple @change="chooseFiles">
          </label>
        </div>
        <ul v-if="saved?.attachments.length || queued.length" class="attachment-list">
          <li v-for="attachment in saved?.attachments" :key="attachment.id">
            <a :href="`/api/checkups/${saved.id}/attachments/${attachment.id}`">{{ attachment.filename || '附件' }}</a>
            <small>{{ attachmentKinds[attachment.kind] || attachment.kind }}</small>
          </li>
          <li v-for="(item, index) in queued" :key="index">
            <span>{{ item.file.name }}</span><small>{{ attachmentKinds[item.kind] }} · 待上传</small>
            <button class="button-text" type="button" :aria-label="`移除 ${item.file.name}`" @click="queued.splice(index, 1)">移除</button>
          </li>
        </ul>
      </section>

      <section class="panel fields">
        <h2>医嘱与小结</h2>
        <label class="field"><span>小结</span><textarea v-model="field.summary" rows="2" maxlength="6000"></textarea></label>
        <label class="field"><span>医嘱</span><textarea v-model="field.advice" rows="2" maxlength="6000"></textarea></label>
      </section>

      <section class="panel fields">
        <h2>下次预约</h2>
        <div class="field-row">
          <label class="field"><span>预约日期</span><input v-model="field.next_visit_date" type="date" :min="field.visit_date"></label>
          <label class="field"><span>预约时间</span><input v-model="field.next_visit_time" type="time"></label>
        </div>
      </section>

      <section class="panel fields">
        <h2>家人查看</h2>
        <label class="check-field"><input v-model="field.viewer_visible" type="checkbox">允许家人查看这条记录</label>
        <label class="field"><span>写给家人的说明</span><textarea v-model="field.viewer_note" rows="2" maxlength="2000"></textarea></label>
      </section>
    </fieldset>

    <div class="editor-actions sticky-actions">
      <p v-if="error" class="form-message" role="alert">{{ error }}</p>
      <button class="button-primary" type="submit" :disabled="saving">{{ saving ? '正在保存…' : '保存产检记录' }}</button>
    </div>
  </form>

  <button v-if="saved && !deleting" class="button-text" type="button" :disabled="saving" @click="deleting = true">删除这条记录</button>
  <section v-if="deleting" class="panel fields delete-confirm" aria-label="确认删除">
    <h2>删除这条产检记录？</h2>
    <p>这条产检记录和附件将从列表移除。</p>
    <div class="button-row">
      <button class="button-secondary" type="button" :disabled="saving" @click="deleting = false">取消</button>
      <button class="button-danger" type="button" :disabled="saving" @click="remove">确认删除</button>
    </div>
  </section>
</template>
