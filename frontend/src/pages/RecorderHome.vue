<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { api } from '../api/recorder'
import CheckupForm from '../components/CheckupForm.vue'
import MilestoneSettings from '../components/MilestoneSettings.vue'
import PregnancyForm from '../components/PregnancyForm.vue'
import { displayTime, gestationLabel, sources } from '../components/pregnancy'

const session = ref(null)
const snapshot = ref(null)
const records = ref([])
const options = ref([])
const setupToken = ref('')
const password = ref('')
const confirmPassword = ref('')
const view = ref('home')
const selected = ref(null)
const busy = ref(true)
const error = ref('')
const notice = ref('')
const page = ref(null)
const isSetup = computed(() => Boolean(setupToken.value && !session.value?.configured))
const pregnancy = computed(() => snapshot.value?.pregnancy)
const nextVisit = computed(() => {
  const today = snapshot.value?.today || ''
  return records.value
    .filter(record => record.next_visit_date && record.next_visit_date >= today)
    .sort((a, b) => (a.next_visit_date + (a.next_visit_time || '')).localeCompare(
      b.next_visit_date + (b.next_visit_time || ''),
    ))[0]
})
const countdown = computed(() => {
  const days = pregnancy.value.days_until_due
  if (days === 0) return '今天是预产期'
  return days > 0 ? `距预产期还有 ${days} 天` : `已过预产期 ${-days} 天`
})

function readSetupLink() {
  const token = new URLSearchParams(window.location.hash.slice(1)).get('setup')
  if (!token) return
  setupToken.value = token
  window.history.replaceState(null, '', window.location.pathname + window.location.search)
}

async function changeView(target) {
  view.value = target
  await nextTick()
  window.scrollTo(0, 0)
  page.value?.focus({ preventScroll: true })
}

function fail(problem) {
  if (problem.status === 401 && session.value?.authenticated) {
    session.value = { authenticated: false, configured: true }
    snapshot.value = null
    records.value = []
    selected.value = null
    view.value = 'home'
    error.value = '登录已过期，请重新登录。'
    return
  }
  error.value = problem.message
}

async function loadDashboard() {
  const [current, checkups, definitions] = await Promise.all([
    api('/pregnancy'), api('/checkups'), api('/metrics/definitions'),
  ])
  snapshot.value = current
  records.value = checkups
  options.value = definitions
}

async function load() {
  busy.value = true
  error.value = ''
  try {
    session.value = await api('/auth/session')
    if (session.value.authenticated) await loadDashboard()
  } catch (problem) {
    fail(problem)
  } finally {
    busy.value = false
  }
}

async function authenticate() {
  error.value = ''
  if (isSetup.value && password.value !== confirmPassword.value) {
    error.value = '两次输入的口令不一致。'
    return
  }
  busy.value = true
  try {
    session.value = await api(isSetup.value ? '/auth/setup' : '/auth/login', {
      method: 'POST',
      data: isSetup.value ? { token: setupToken.value, password: password.value } : { password: password.value },
    })
    setupToken.value = ''
    password.value = ''
    confirmPassword.value = ''
    await loadDashboard()
    await changeView('home')
  } catch (problem) {
    fail(problem)
  } finally {
    busy.value = false
  }
}

async function logout() {
  if (view.value !== 'home') return
  busy.value = true
  error.value = ''
  try {
    await api('/auth/logout', { method: 'POST' })
    session.value = { authenticated: false, configured: true }
    snapshot.value = null
    records.value = []
    selected.value = null
    notice.value = ''
    try {
      for (const key of Object.keys(sessionStorage)) {
        if (key.startsWith('preg.checkup.')) sessionStorage.removeItem(key)
      }
    } catch {}
  } catch (problem) {
    fail(problem)
  } finally {
    busy.value = false
  }
}

async function openCheckup(id = null) {
  busy.value = true
  notice.value = ''
  error.value = ''
  try {
    selected.value = id ? await api(`/checkups/${id}`) : null
    await changeView('checkup')
  } catch (problem) {
    fail(problem)
  } finally {
    busy.value = false
  }
}

async function closeEditor() {
  error.value = ''
  await changeView('home')
  busy.value = true
  try {
    await loadDashboard()
  } catch (problem) {
    fail(problem)
  } finally {
    busy.value = false
  }
}

function pregnancySaved(updated) {
  snapshot.value = updated
  notice.value = '已保存预产期'
  changeView('home')
}

function checkupSaved(message) {
  notice.value = message
  closeEditor()
}

onMounted(() => {
  readSetupLink()
  window.addEventListener('hashchange', readSetupLink)
  load()
})
onBeforeUnmount(() => window.removeEventListener('hashchange', readSetupLink))
</script>

<template>
  <main ref="page" class="recorder-shell" tabindex="-1">
    <header class="app-header">
      <span class="app-name">孕期陪伴</span>
      <div v-if="session?.authenticated && view === 'home'" class="settings-controls">
        <button class="button-text" type="button" :disabled="busy" @click="changeView('milestones')">里程碑与日历</button>
        <button class="button-text" type="button" :disabled="busy" @click="logout">退出登录</button>
      </div>
    </header>

    <section v-if="!session" class="auth-panel panel">
      <h1>{{ busy ? '正在连接…' : '暂时无法连接' }}</h1>
      <p v-if="error" class="form-message" role="alert">{{ error }}</p>
      <button v-if="!busy" class="button-secondary" type="button" @click="load">重试</button>
    </section>

    <section v-else-if="!session.authenticated" class="auth-panel panel">
      <h1>{{ isSetup ? '设置记录口令' : '记录者登录' }}</h1>
      <form v-if="session.configured || isSetup" class="fields" @submit.prevent="authenticate">
        <label class="field">
          <span>口令 <small v-if="isSetup">至少 12 个字符</small></span>
          <input v-model="password" type="password" name="password" :autocomplete="isSetup ? 'new-password' : 'current-password'"
            :minlength="isSetup ? 12 : 1" maxlength="128" required>
        </label>
        <label v-if="isSetup" class="field">
          <span>再输入一次口令</span>
          <input v-model="confirmPassword" type="password" name="confirm-password" autocomplete="new-password" minlength="12" maxlength="128" required>
        </label>
        <p v-if="error" class="form-message" role="alert">{{ error }}</p>
        <button class="button-primary" type="submit" :disabled="busy">
          {{ busy ? '请稍候…' : isSetup ? '设置并登录' : '登录' }}
        </button>
      </form>
      <p v-else>请打开管理员发给你的首次设置链接。</p>
    </section>

    <template v-else>
      <p v-if="error" class="form-message" role="alert">{{ error }}</p>
      <div v-if="!snapshot" class="panel fields">
        <p>{{ busy ? '正在读取记录…' : '暂时无法读取记录。' }}</p>
        <button v-if="!busy" class="button-secondary" type="button" @click="load">重试</button>
      </div>

      <PregnancyForm v-else-if="view === 'pregnancy'" :snapshot="snapshot"
        @saved="pregnancySaved" @close="changeView('home')" @failed="fail" />
      <MilestoneSettings v-else-if="view === 'milestones'" @close="changeView('home')" @failed="fail" />
      <CheckupForm v-else-if="view === 'checkup'" :record="selected" :snapshot="snapshot"
        :options="options" :previous="records[0]" @saved="checkupSaved" @close="closeEditor" @failed="fail" />

      <template v-else>
        <p v-if="notice" class="toast" role="status">{{ notice }}</p>
        <div class="page-heading">
          <h1>今天</h1>
          <time :datetime="snapshot.today">{{ snapshot.today }}</time>
        </div>
        <div class="home-cards">
          <section v-if="pregnancy" class="pregnancy-card">
            <div class="section-heading">
              <h2>当前孕周</h2>
              <button class="button-on-primary" type="button" @click="changeView('pregnancy')">预产期设置</button>
            </div>
            <p class="week-number">{{ gestationLabel(pregnancy.ga_days) }}</p>
            <p>{{ countdown }}</p>
            <p class="due-caption">预产期 {{ pregnancy.edd_date }} · {{ sources[pregnancy.edd_source] || pregnancy.edd_source }}</p>
          </section>
          <section v-else class="panel fields">
            <h2>设置预产期</h2>
            <p>填入预产期后，就能查看当前孕周并录入产检。</p>
            <button class="button-primary" type="button" @click="changeView('pregnancy')">设置预产期</button>
          </section>
          <section v-if="nextVisit" class="appointment-card panel">
            <h2>下次产检</h2>
            <p><strong>{{ nextVisit.next_visit_date }} {{ displayTime(nextVisit.next_visit_time) }}</strong></p>
            <p v-if="nextVisit.hospital">{{ nextVisit.hospital }}</p>
          </section>
        </div>

        <section class="checkup-section">
          <div class="section-heading">
            <h2>产检记录</h2>
            <button v-if="pregnancy" class="button-primary" type="button" :disabled="busy" @click="openCheckup()">录入产检</button>
          </div>
          <p v-if="!records.length" class="panel empty-records">还没有产检记录。</p>
          <ul v-else class="record-list">
            <li v-for="record in records" :key="record.id">
              <button class="record-button panel" type="button" :disabled="busy" @click="openCheckup(record.id)">
                <span><strong>{{ record.visit_date }}</strong><small>{{ [record.hospital, record.doctor].filter(Boolean).join(' · ') || '产检记录' }}</small></span>
                <span class="record-age">{{ gestationLabel(record.ga_days) }}</span>
              </button>
            </li>
          </ul>
        </section>
      </template>
    </template>
  </main>
</template>
