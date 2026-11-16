<script setup>
import { computed, onMounted, ref } from 'vue'
import { api } from '../api/recorder'

const props = defineProps({
  section: { type: String, required: true },
  today: { type: String, required: true },
  checkups: { type: Array, required: true },
})
const emit = defineEmits(['close', 'switch', 'failed'])
const isNote = computed(() => props.section === 'notes')
const path = computed(() => '/' + props.section)
const items = ref([])
const form = ref(null)
const removing = ref(null)
const busy = ref(false)
const error = ref('')
const notice = ref('')
const states = { open: '待问', asked: '已问', answered: '已解答' }

function fail(problem) {
  if (problem.status === 401) emit('failed', problem)
  else error.value = problem.message
}

async function load() {
  busy.value = true
  error.value = ''
  try { items.value = await api(path.value) } catch (problem) { fail(problem) }
  finally { busy.value = false }
}
onMounted(load)

function edit(item = null) {
  error.value = ''
  notice.value = ''
  removing.value = null
  const identity = { id: item?.id, version: item?.version }
  form.value = isNote.value ? {
    ...identity, occurred_on: item?.occurred_on || props.today,
    title: item?.title || '', body: item?.body || '', tags: item?.tags.join('、') || '',
    viewer_visible: item?.viewer_visible ?? false,
  } : {
    ...identity, text: item?.text || '', status: item?.status || 'open',
    checkup_id: item?.checkup_id || null, answer: item?.answer || '',
  }
}

async function save() {
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    const { id, ...data } = form.value
    if (isNote.value) data.tags = [...new Set(data.tags.split(/[、,，]/u).map(tag => tag.trim()).filter(Boolean))]
    await api(id ? `${path.value}/${id}` : path.value, { method: id ? 'PUT' : 'POST', data })
    form.value = null
    notice.value = isNote.value ? '已保存备注。' : '已保存问题。'
    items.value = await api(path.value)
  } catch (problem) { fail(problem) }
  finally { busy.value = false }
}

async function remove(item) {
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    await api(`${path.value}/${item.id}?version=${item.version}`, { method: 'DELETE' })
    items.value = items.value.filter(entry => entry.id !== item.id)
    removing.value = null
    notice.value = isNote.value ? '已删除备注。' : '已删除问题。'
  } catch (problem) { fail(problem) }
  finally { busy.value = false }
}
</script>

<template>
  <div class="page-heading">
    <h1>{{ isNote ? '备注' : '待问医生' }}</h1>
    <button class="button-text" type="button" :disabled="busy" @click="emit('close')">返回</button>
  </div>
  <div class="section-heading entry-heading">
    <button class="button-text" type="button" :disabled="busy || !!form" @click="emit('switch', isNote ? 'questions' : 'notes')">
      {{ isNote ? '查看问题清单' : '查看备注' }}
    </button>
    <button v-if="!form" class="button-primary" type="button" :disabled="busy" @click="edit()">{{ isNote ? '写备注' : '添加问题' }}</button>
  </div>
  <section class="panel fields">
    <form v-if="form" class="fields" @submit.prevent="save">
      <template v-if="isNote">
        <div class="field-row">
          <label class="field"><span>发生日期</span><input v-model="form.occurred_on" type="date" required></label>
          <label class="field"><span>标题 <small>选填</small></span><input v-model="form.title" maxlength="100"></label>
        </div>
        <label class="field"><span>备注内容</span><textarea v-model="form.body" maxlength="6000" rows="4" required></textarea></label>
        <label class="field"><span>标签 <small>用逗号或顿号分隔</small></span><input v-model="form.tags" maxlength="465"></label>
        <label class="check-field"><input v-model="form.viewer_visible" type="checkbox">允许家人查看这条备注</label>
      </template>
      <template v-else>
        <label class="field"><span>想问的问题</span><textarea v-model="form.text" maxlength="1000" rows="3" required></textarea></label>
        <div class="field-row">
          <label class="field"><span>状态</span>
            <select v-model="form.status"><option v-for="(label, value) in states" :key="value" :value="value">{{ label }}</option></select>
          </label>
          <label class="field"><span>关联产检 <small>选填</small></span>
            <select v-model="form.checkup_id">
              <option :value="null">选择产检记录</option>
              <option v-if="form.checkup_id && !checkups.some(entry => entry.id === form.checkup_id)" :value="form.checkup_id">已移除的产检</option>
              <option v-for="entry in checkups" :key="entry.id" :value="entry.id">{{ entry.visit_date }} {{ entry.hospital }}</option>
            </select>
          </label>
        </div>
        <label class="field"><span>医生回复 <small>选填</small></span><textarea v-model="form.answer" maxlength="4000" rows="3"></textarea></label>
      </template>
      <div class="settings-controls">
        <button class="button-secondary" type="button" :disabled="busy" @click="form = null">取消</button>
        <button class="button-primary" type="submit" :disabled="busy">{{ isNote ? '保存备注' : '保存问题' }}</button>
      </div>
    </form>

    <p v-if="notice" class="preview-line" role="status">{{ notice }}</p>
    <p v-if="error" class="form-message" role="alert">{{ error }}</p>
    <button v-if="error && !form && !items.length" class="button-text settings-action" type="button" :disabled="busy" @click="load">重新加载</button>

    <ul v-if="items.length" class="settings-list">
      <li v-for="item in items" :key="item.id">
        <template v-if="isNote">
          <div class="section-heading"><strong>{{ item.title || '备注' }}</strong><time class="settings-help">{{ item.occurred_on }}</time></div>
          <p class="entry-content">{{ item.body }}</p>
          <div v-if="item.tags.length" class="settings-controls"><span v-for="tag in item.tags" :key="tag" class="entry-state">{{ tag }}</span></div>
        </template>
        <template v-else>
          <div class="section-heading">
            <strong class="entry-content">{{ item.text }}</strong>
            <span class="entry-state" :data-done="item.status === 'answered'">{{ states[item.status] }}</span>
          </div>
          <p v-if="item.answer" class="entry-content settings-help">{{ item.answer }}</p>
        </template>
        <div v-if="removing === item.id" class="settings-controls">
          <span>删除这条{{ isNote ? '备注' : '问题' }}？</span>
          <button class="button-secondary" type="button" :disabled="busy" @click="removing = null">取消</button>
          <button class="button-danger" type="button" :disabled="busy" @click="remove(item)">确认删除</button>
        </div>
        <div v-else class="settings-controls">
          <button class="button-text" type="button" :disabled="busy || !!form" @click="edit(item)">编辑</button>
          <button class="button-text" type="button" :disabled="busy || !!form" @click="removing = item.id">删除</button>
        </div>
      </li>
    </ul>
    <p v-else-if="!busy && !form && !error" class="settings-help">{{ isNote ? '还没有备注。' : '还没有待问医生的问题。' }}</p>
  </section>
</template>
