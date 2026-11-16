<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api/recorder'

const emit = defineEmits(['failed'])
const subscriptions = ref([])
const busy = ref(true)
const error = ref('')
const label = ref('')
const duration = ref('')
const newLink = ref('')
const newLinkId = ref(null)
const linkInput = ref(null)
const notice = ref('')
const revoking = ref(null)

const stateLabel = { active: '有效', expired: '已过期', revoked: '已吊销' }

function fail(problem) {
  if (problem.status === 401) emit('failed', problem)
  else error.value = problem.message
}

async function load() {
  busy.value = true
  error.value = ''
  try {
    subscriptions.value = await api('/share-tokens')
  } catch (problem) {
    fail(problem)
  } finally {
    busy.value = false
  }
}

async function createLink() {
  busy.value = true
  error.value = ''
  notice.value = ''
  try {
    const created = await api('/share-tokens', {
      method: 'POST',
      data: { label: label.value, expires_in_days: duration.value || null },
    })
    const { path, public_origin: origin, ...subscription } = created
    newLink.value = new URL(path, origin || window.location.origin).href
    newLinkId.value = subscription.id
    subscriptions.value.unshift(subscription)
    label.value = ''
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
      notice.value = '已复制订阅链接。'
      return
    }
  } catch {}
  linkInput.value?.focus()
  linkInput.value?.select()
  notice.value = '已选中链接，请复制。'
}

async function revoke() {
  busy.value = true
  error.value = ''
  notice.value = ''
  const id = revoking.value
  try {
    await api(`/share-tokens/${id}`, { method: 'DELETE' })
    if (newLinkId.value === id) {
      newLink.value = ''
      newLinkId.value = null
    }
    const subscription = subscriptions.value.find(item => item.id === id)
    if (subscription) subscription.state = 'revoked'
    revoking.value = null
    notice.value = '已吊销链接。'
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
    <h2 id="calendar-heading">ICS 日历订阅</h2>
    <p class="settings-help">将链接添加到手机的日历订阅。日历使用通用标题，产检仅同步允许家人查看的下次预约。</p>
    <form class="fields" @submit.prevent="createLink">
      <div class="field-row">
        <label class="field"><span>链接名称 <small>选填</small></span><input v-model="label" maxlength="80" placeholder="例如：我的手机"></label>
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
      <button class="button-primary settings-action" type="submit" :disabled="busy">生成订阅链接</button>
    </form>

    <div v-if="newLink" class="fields calendar-new-link">
      <p>完整链接仅在本次生成后显示。请复制到日历订阅设置。</p>
      <label class="field"><span>订阅链接</span><input ref="linkInput" :value="newLink" readonly></label>
      <div class="settings-controls">
        <button class="button-secondary" type="button" @click="copyLink">复制链接</button>
        <a class="button-text calendar-link" :href="newLink" download="preg-companion.ics" referrerpolicy="no-referrer">下载 ICS</a>
      </div>
    </div>
    <p v-if="notice" class="preview-line" role="status">{{ notice }}</p>
    <p v-if="error" class="form-message" role="alert">{{ error }}</p>

    <ul v-if="subscriptions.length" class="settings-list">
      <li v-for="item in subscriptions" :key="item.id">
        <div class="section-heading">
          <div>
            <strong>{{ item.label || '日历订阅' }}</strong>
            <p class="settings-help">
              {{ stateLabel[item.state] }}
              <template v-if="item.expires_at"> · {{ new Date(item.expires_at).toLocaleDateString('zh-CN') }} 到期</template>
            </p>
          </div>
          <button v-if="item.state === 'active' && revoking !== item.id" class="button-text" type="button"
            :disabled="busy" @click="revoking = item.id">吊销</button>
        </div>
        <div v-if="revoking === item.id" class="fields calendar-confirm">
          <p>吊销后，这个链接将停止刷新。日历里已下载的事件可能仍保留。</p>
          <div class="settings-controls">
            <button class="button-secondary" type="button" :disabled="busy" @click="revoking = null">取消</button>
            <button class="button-danger" type="button" :disabled="busy" @click="revoke">确认吊销</button>
          </div>
        </div>
      </li>
    </ul>
    <p v-else-if="!busy && !error" class="settings-help">还没有订阅链接。</p>
    <button v-if="error && !subscriptions.length" class="button-text settings-action" type="button" :disabled="busy" @click="load">重新加载</button>
  </section>
</template>
