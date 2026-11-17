<script setup>
import ConfirmTip from './ConfirmTip.vue'
import { onMounted, ref } from 'vue'
import { showTip, watchError } from '../tips'
import { api } from '../api/recorder'

const props = defineProps({ scope: { type: String, default: 'calendar' } })
const calendar = props.scope === 'calendar'
const heading = calendar ? 'ICS 日历订阅' : '家人查看链接'
const emit = defineEmits(['failed'])
const subscriptions = ref([])
const busy = ref(true)
const error = ref('')
watchError(error)
const label = ref('')
const duration = ref('')
const newLink = ref('')
const newLinkId = ref(null)
const linkInput = ref(null)
const revoking = ref(null)
const linkHelp = calendar
  ? '请将链接添加到手机的日历订阅。允许家人查看的产检会同步下次预约，医院显示在地点栏。'
  : '持有链接的家人可以查看你设为可见的记录和指标。可以为不同家人生成独立链接。'
const revokeMessage = calendar
  ? '吊销后链接立即停止同步。已下载的日程由日历应用管理。'
  : '吊销后链接立即失效，已打开的家人页也会关闭共享内容。'

const stateLabel = { active: '有效', expired: '已过期', revoked: '已吊销' }

function fail(problem) {
  if (problem.status === 401) emit('failed', problem)
  else error.value = problem.message
}

async function load() {
  busy.value = true
  error.value = ''
  try {
    subscriptions.value = await api('/share-tokens?scope=' + props.scope)
  } catch (problem) {
    fail(problem)
  } finally {
    busy.value = false
  }
}

async function createLink() {
  busy.value = true
  error.value = ''
  try {
    const created = await api('/share-tokens', {
      method: 'POST',
      data: { scope: props.scope, label: label.value, expires_in_days: duration.value || null },
    })
    const { path, public_origin: origin, ...subscription } = created
    newLink.value = new URL(path, origin || window.location.origin).href
    newLinkId.value = subscription.id
    subscriptions.value.unshift(subscription)
    label.value = ''
    showTip('链接已生成，请复制保存。完整链接仅在本次生成后显示。')
  } catch (problem) {
    fail(problem)
  } finally {
    busy.value = false
  }
}

async function copyLink() {
  try {
    if (navigator.clipboard) {
      await navigator.clipboard.writeText(newLink.value)
      showTip(calendar ? '已复制订阅链接。' : '已复制家人查看链接。', 'success')
      return
    }
  } catch {}
  linkInput.value?.focus()
  linkInput.value?.select()
  showTip('已选中链接，请复制。')
}

async function revoke() {
  busy.value = true
  error.value = ''
  const id = revoking.value
  try {
    await api(`/share-tokens/${id}?scope=${props.scope}`, { method: 'DELETE' })
    if (newLinkId.value === id) {
      newLink.value = ''
      newLinkId.value = null
    }
    const subscription = subscriptions.value.find(item => item.id === id)
    if (subscription) subscription.state = 'revoked'
    revoking.value = null
    showTip('已吊销链接，立即生效。', 'success')
  } catch (problem) {
    fail(problem)
  } finally {
    busy.value = false
  }
}

onMounted(load)
</script>

<template>
  <section class="panel fields" aria-labelledby="calendar-heading">
    <div class="section-heading">
      <h2 id="calendar-heading">{{ heading }}</h2>
      <button class="button-text" type="button" @click="showTip(linkHelp)">链接说明</button>
    </div>
    <form class="fields" @submit.prevent="createLink">
      <div class="field-row">
        <label class="field"><span>链接名称 <small>选填</small></span><input v-model="label" maxlength="80" :placeholder="calendar ? '例如：我的手机' : '例如：家人'"></label>
        <label class="field">
          <span>有效期</span>
          <select v-model="duration">
            <option value="">使用服务器默认值</option>
            <option :value="30">30 天</option>
            <option :value="90">90 天</option>
            <option :value="365">365 天</option>
          </select>
        </label>
      </div>
      <button class="button-primary settings-action" type="submit" :disabled="busy">{{ calendar ? '生成订阅链接' : '生成家人查看链接' }}</button>
    </form>

    <div v-if="newLink" class="fields calendar-new-link">
      <label class="field"><span>{{ calendar ? '订阅链接' : '家人查看链接' }}</span><input ref="linkInput" :value="newLink" readonly></label>
      <div class="settings-controls">
        <button class="button-secondary" type="button" @click="copyLink">复制链接</button>
        <a v-if="calendar" class="button-text calendar-link" :href="newLink" download="preg-companion.ics" referrerpolicy="no-referrer">下载 ICS</a>
        <a v-else class="button-text calendar-link" :href="newLink" target="_blank" rel="noopener noreferrer">预览家人页</a>
      </div>
    </div>

    <ul v-if="subscriptions.length" class="settings-list">
      <li v-for="item in subscriptions" :key="item.id">
        <div class="section-heading">
          <div>
            <strong>{{ item.label || heading }}</strong>
            <p class="settings-help">
              {{ stateLabel[item.state] }}
              <template v-if="item.state === 'active' && item.expires_at"> · {{ new Date(item.expires_at).toLocaleDateString('zh-CN') }} 到期</template>
              <template v-if="item.state === 'revoked' && item.revoked_at"> · {{ new Date(item.revoked_at).toLocaleString('zh-CN') }}</template>
            </p>
          </div>
          <button v-if="item.state === 'active'" class="button-text" type="button"
            :disabled="busy || (revoking !== null && revoking !== item.id)" @click="revoking = item.id">吊销</button>
        </div>
        <ConfirmTip v-if="revoking === item.id" :message="revokeMessage" action="确认吊销"
          :busy="busy" @cancel="revoking = null" @confirm="revoke" />
      </li>
    </ul>
    <p v-else-if="!busy && !error" class="settings-help">{{ calendar ? '还没有订阅链接。' : '还没有家人查看链接。' }}</p>
    <button v-if="error && !subscriptions.length" class="button-text settings-action" type="button" :disabled="busy" @click="load">重新加载</button>
  </section>
</template>
