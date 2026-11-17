<script setup>
import { nextTick, ref, watch } from 'vue'
import { showTip } from '../tips'
import { api } from '../api/recorder'
import ConfirmTip from './ConfirmTip.vue'
import DayPicker from './DayPicker.vue'
import { mealLabels as meals } from './meals'

const props = defineProps({ today: { type: String, required: true }, focusSymptoms: Boolean, recipeMeal: Object })
const emit = defineEmits(['close', 'failed', 'meal-handled'])
const day = ref(props.today)
const record = ref(null)
const busy = ref(false)
const custom = ref('')
const queued = ref({})
const removePhotos = ref({})
const symptomsSection = ref(null)
const photoDialog = ref(null)
const photoMeal = ref(null)
const cameraInput = ref(null)
const pictureInput = ref(null)
const mealToReplace = ref(null)
const photoTypes = 'image/jpeg,image/png,image/webp'
const symptomChoices = ['恶心', '反酸', '乏力', '头晕', '胃口变化', '睡眠不佳']

function fail(problem) {
  if (problem.status === 401) emit('failed', problem)
  else showTip(problem.message, 'error')
}

async function load() {
  busy.value = true
  record.value = null
  custom.value = ''
  queued.value = {}
  removePhotos.value = {}
  try {
    const snapshot = await api(`/daily/${day.value}`)
    try {
      const draft = JSON.parse(sessionStorage.getItem('preg.daily.' + day.value))
      if (draft?.version === snapshot.version) {
        Object.assign(snapshot, draft.fields)
        showTip('已恢复此标签页的草稿。')
      }
    } catch {}
    record.value = snapshot
  } catch (problem) {
    fail(problem)
  } finally {
    busy.value = false
  }
  if (!record.value || !props.recipeMeal || day.value !== props.today) return
  const { kind, text } = props.recipeMeal
  if (record.value.meals[kind]?.trim() && record.value.meals[kind] !== text) {
    mealToReplace.value = props.recipeMeal
  } else {
    applyMeal(props.recipeMeal)
  }
}

function finishMeal() {
  mealToReplace.value = null
  emit('meal-handled')
}

function applyMeal({ kind, text }) {
  record.value.meals[kind] = text
  finishMeal()
  showTip(`已带入${meals[kind]}草稿。`, 'success')
}

if (props.focusSymptoms) {
  const stop = watch(record, async value => {
    if (!value) return
    await nextTick()
    symptomsSection.value?.scrollIntoView({ block: 'start' })
    stop()
  })
}

function fields(value) {
  const { version, mood, note, viewer_visible, meals, symptoms } = value
  return { version, mood, note, viewer_visible, meals, symptoms }
}

watch(record, value => {
  if (!value || busy.value) return
  try {
    const draft = { version: value.version, fields: fields(value) }
    sessionStorage.setItem('preg.daily.' + value.log_date, JSON.stringify(draft))
  } catch {}
}, { deep: true, flush: 'sync' })

watch(day, load, { immediate: true })

function toggleSymptom(tag) {
  const list = record.value.symptoms
  const position = list.indexOf(tag)
  if (position >= 0) list.splice(position, 1)
  else if (list.length < 20) list.push(tag)
  else showTip('一天最多添加 20 个症状标签。', 'error')
}

function addSymptom() {
  const tag = custom.value.trim()
  if (tag && !record.value.symptoms.includes(tag)) toggleSymptom(tag)
  custom.value = ''
}

function openPhotoDialog(kind) {
  photoMeal.value = kind
  photoDialog.value.showModal()
}

function pickPhoto(input) {
  photoDialog.value.close()
  input.click()
}

function choosePhoto(event) {
  const file = event.target.files[0]
  event.target.value = ''
  if (!file || !photoMeal.value || busy.value) return
  if (file.size > 20 * 1024 * 1024) {
    showTip('每张照片最多 20 MB。', 'error')
    return
  }
  const kind = photoMeal.value
  queued.value[kind] = file
  delete removePhotos.value[kind]
}

async function save() {
  const path = `/daily/${day.value}`
  busy.value = true
  let savedText = false
  try {
    record.value = await api(path, { method: 'PUT', data: fields(record.value) })
    savedText = true
    try { sessionStorage.removeItem('preg.daily.' + day.value) } catch {}
    for (const kind of Object.keys(removePhotos.value)) {
      record.value = await api(`${path}/meals/${kind}/photo?version=${record.value.version}`, { method: 'DELETE' })
      delete removePhotos.value[kind]
    }
    for (const [kind, file] of Object.entries(queued.value)) {
      const data = new FormData()
      data.append('file', file)
      record.value = await api(`${path}/meals/${kind}/photo?version=${record.value.version}`, { method: 'POST', data })
      delete queued.value[kind]
    }
    showTip('已保存每日记录。', 'success')
  } catch (problem) {
    if (savedText && problem.status !== 401) showTip(`文字已保存，照片尚未处理完。${problem.message}`, 'error')
    else fail(problem)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="page-heading">
    <h1>每日记录</h1>
    <button class="button-text" type="button" :disabled="busy" @click="emit('close')">返回</button>
  </div>
  <DayPicker v-model="day" :busy="busy || !!mealToReplace" />
  <div v-if="!record" class="panel fields">
    <p v-if="busy">正在读取记录…</p>
    <button v-if="!busy" class="button-secondary" type="button" @click="load">重试</button>
  </div>

  <form v-else class="editor checkup-editor" @submit.prevent="save">
    <fieldset :disabled="busy || !!mealToReplace">
      <section class="panel fields">
        <h2>饮食</h2>
        <div class="field-row">
          <div v-for="(label, kind) in meals" :key="kind" class="meal-card fields">
            <h3>{{ label }}</h3>
            <div class="field meal-field">
              <input v-model="record.meals[kind]" maxlength="500" placeholder="记一句就好" :aria-label="`${label}吃了什么`">
              <button class="button-text meal-camera" type="button" aria-haspopup="dialog"
                :aria-label="`${record.photos[kind] || queued[kind] ? '更换' : '添加'}${label}照片`"
                @click="openPhotoDialog(kind)">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"
                  stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
                  <path d="M4.5 7h3l1.7-2.5h5.6L16.5 7h3A2.5 2.5 0 0 1 22 9.5v7A2.5 2.5 0 0 1 19.5 19h-15A2.5 2.5 0 0 1 2 16.5v-7A2.5 2.5 0 0 1 4.5 7Z" />
                  <circle cx="12" cy="12.75" r="3.25" />
                </svg>
              </button>
            </div>
            <img v-if="record.photos[kind] && !removePhotos[kind] && !queued[kind]"
              class="meal-image" :src="`/api/daily/${day}/meals/${kind}/photo/${record.photos[kind].id}`"
              :alt="`${label}照片`" loading="lazy">
            <div v-if="queued[kind]" class="section-heading meal-pending">
              <small>{{ queued[kind].name }} · 待上传</small>
              <button class="button-text" type="button" @click="delete queued[kind]">取消选择</button>
            </div>
            <button v-else-if="record.photos[kind]" class="button-text settings-action" type="button"
              @click="removePhotos[kind] ? delete removePhotos[kind] : removePhotos[kind] = true">
              {{ removePhotos[kind] ? '保留照片' : '移除照片' }}
            </button>
          </div>
        </div>
      </section>

      <section ref="symptomsSection" class="panel fields">
        <h2>症状</h2>
        <div class="settings-controls">
          <button v-for="tag in [...new Set([...symptomChoices, ...record.symptoms])]" :key="tag" class="button-text entry-chip"
            type="button" :aria-pressed="record.symptoms.includes(tag)" @click="toggleSymptom(tag)">{{ tag }}</button>
        </div>
        <div class="tag-input">
          <label class="field"><span>自定义标签</span><input v-model="custom" maxlength="40" @keydown.enter.prevent="addSymptom"></label>
          <button class="button-secondary" type="button" @click="addSymptom">添加标签</button>
        </div>
      </section>

      <section class="panel fields">
        <h2>情绪与备注</h2>
        <label class="field"><span>今天的心情</span><input v-model="record.mood" maxlength="60"></label>
        <label class="field"><span>当天备注</span><textarea v-model="record.note" rows="3" maxlength="4000"></textarea></label>
        <label class="check-field"><input v-model="record.viewer_visible" type="checkbox">允许家人查看这条记录</label>
      </section>
    </fieldset>
    <div class="editor-actions sticky-actions">
      <button class="button-primary" type="submit" :disabled="busy || !!mealToReplace">{{ busy ? '正在保存…' : '保存当天记录' }}</button>
    </div>
  </form>

  <ConfirmTip v-if="mealToReplace" :message="`${meals[mealToReplace.kind]}已有记录，要替换草稿内容吗？`" action="替换"
    @cancel="finishMeal" @confirm="applyMeal(mealToReplace)" />

  <dialog ref="photoDialog" class="meal-photo-dialog" aria-labelledby="meal-photo-title">
    <h2 id="meal-photo-title">{{ meals[photoMeal] }}照片</h2>
    <div class="meal-photo-actions">
      <button class="button-secondary" type="button" @click="pickPhoto(cameraInput)">拍照</button>
      <button class="button-secondary" type="button" @click="pickPhoto(pictureInput)">从相册或文件选择</button>
      <button class="button-text" type="button" @click="photoDialog.close()">取消</button>
    </div>
  </dialog>
  <input ref="cameraInput" type="file" :accept="photoTypes" capture="environment" hidden @change="choosePhoto">
  <input ref="pictureInput" type="file" :accept="photoTypes" hidden @change="choosePhoto">
</template>
