<script setup>
import TipHost from '../components/TipHost.vue'
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'
import { showTip, showValidationTip } from '../tips'
import { api } from '../api/recorder'
import AppBrand from '../components/AppBrand.vue'
import CheckupForm from '../components/CheckupForm.vue'
import DailyJournal from '../components/DailyJournal.vue'
import JournalCalendar from '../components/JournalCalendar.vue'
import MilestoneSettings from '../components/MilestoneSettings.vue'
import NotesQuestions from '../components/NotesQuestions.vue'
import PregnancyForm from '../components/PregnancyForm.vue'
import RecorderTrends from '../components/RecorderTrends.vue'
import ShareLinks from '../components/ShareLinks.vue'
import RecordingShortcuts from '../components/RecordingShortcuts.vue'
import SupplementJournal from '../components/SupplementJournal.vue'
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
const calendarDay = ref('')
const calendarFilter = ref('all')
const calendarDestination = ref(null)
const busy = ref(true)
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
    calendarDestination.value = null
    view.value = 'home'
    showTip('登录已过期，请重新登录。', 'error')
    return
  }
  showTip(problem.message, 'error')
}

function showCalendar() {
  if (!calendarDay.value) calendarDay.value = snapshot.value.today
  calendarDestination.value = null
  changeView('calendar')
}

function returnFromEntry() {
  const destination = calendarDestination.value ? 'calendar' : 'home'
  calendarDestination.value = null
  return changeView(destination)
}

function openCalendarEntry(entry, day) {
  calendarDestination.value = { ...entry, day }
  if (entry.target === 'checkup') return openCheckup(entry.record_id)
  return changeView(entry.target)
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
  if (isSetup.value && password.value !== confirmPassword.value) {
    showTip('两次输入的口令不一致。', 'error')
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
    showTip('已登录。', 'success')
  } catch (problem) {
    fail(problem)
  } finally {
    busy.value = false
  }
}

async function logout() {
  if (view.value !== 'home') return
  busy.value = true
  try {
    await api('/auth/logout', { method: 'POST' })
    session.value = { authenticated: false, configured: true }
    snapshot.value = null
    records.value = []
    selected.value = null
    try {
      for (const key of Object.keys(sessionStorage)) {
        if (key.startsWith('preg.checkup.') || key.startsWith('preg.daily.')) sessionStorage.removeItem(key)
      }
    } catch {}
    showTip('已退出登录。', 'success')
  } catch (problem) {
    fail(problem)
  } finally {
    busy.value = false
  }
}

async function openCheckup(id = null) {
  busy.value = true
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
  await returnFromEntry()
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
  showTip('已保存预产期', 'success')
  returnFromEntry()
}

function checkupSaved(message) {
  showTip(message, 'success')
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
  <main ref="page" class="recorder-shell" tabindex="-1" @invalid.capture="showValidationTip">
    <header class="app-header">
      <AppBrand />
      <div v-if="session?.authenticated && view === 'home'" class="settings-controls">
        <button class="button-text" type="button" :disabled="busy" @click="changeView('milestones')">里程碑与日历</button>
        <button class="button-text" type="button" :disabled="busy" @click="changeView('share')">家人分享</button>
        <button class="button-text" type="button" :disabled="busy" @click="logout">退出登录</button>
      </div>
    </header>

    <section v-if="!session" class="auth-panel panel">
      <h1>{{ busy ? '正在连接…' : '暂时无法连接' }}</h1>
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
        <button class="button-primary" type="submit" :disabled="busy">
          {{ busy ? '请稍候…' : isSetup ? '设置并登录' : '登录' }}
        </button>
      </form>
      <button v-else class="button-text" type="button" @click="showTip('请打开管理员发给你的首次设置链接。')">首次设置说明</button>
    </section>

    <template v-else>
      <div v-if="!snapshot" class="panel fields">
        <p v-if="busy">正在读取记录…</p>
        <button v-if="!busy" class="button-secondary" type="button" @click="load">重试</button>
      </div>

      <JournalCalendar v-else-if="view === 'calendar'" v-model:day="calendarDay" v-model:filter="calendarFilter"
        :today="snapshot.today" @open="openCalendarEntry" @close="changeView('home')" @failed="fail" />
      <PregnancyForm v-else-if="view === 'pregnancy'" :snapshot="snapshot"
        @saved="pregnancySaved" @close="returnFromEntry" @failed="fail" />
      <MilestoneSettings v-else-if="view === 'milestones'" :initial-rule-id="calendarDestination?.record_id"
        @close="returnFromEntry" @failed="fail" />
      <RecorderTrends v-else-if="view === 'trends'" @close="changeView('home')" @failed="fail" />
      <template v-else-if="view === 'share'">
        <div class="page-heading">
          <h1>家人分享</h1>
          <button class="button-text" type="button" @click="changeView('home')">返回</button>
        </div>
        <ShareLinks scope="view" @failed="fail" />
      </template>
      <DailyJournal v-else-if="view === 'daily' || view === 'symptoms'" :today="calendarDestination?.day || snapshot.today"
        :focus-symptoms="view === 'symptoms'" @close="returnFromEntry" @failed="fail" />
      <SupplementJournal v-else-if="view === 'supplements'" :today="calendarDestination?.day || snapshot.today"
        :initial-plan-id="calendarDestination?.record_id" @close="returnFromEntry" @failed="fail" />
      <NotesQuestions v-else-if="view === 'notes' || view === 'questions'" :key="view" :section="view"
        :today="calendarDestination?.day || snapshot.today" :checkups="records"
        :initial-note-id="calendarDestination?.record_id" :new-note="calendarDestination?.target === 'notes' && !calendarDestination.record_id"
        @close="returnFromEntry" @switch="changeView" @failed="fail" />
      <CheckupForm v-else-if="view === 'checkup'" :record="selected" :snapshot="snapshot"
        :options="options" :previous="records[0]" @saved="checkupSaved" @close="closeEditor" @failed="fail" />

      <template v-else>
        <div class="page-heading">
          <h1>今天</h1>
          <div class="settings-controls">
            <time :datetime="snapshot.today">{{ snapshot.today }}</time>
            <button class="button-secondary" type="button" :disabled="busy" @click="showCalendar">日历</button>
          </div>
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
            <button class="button-text settings-action" type="button" @click="showTip('填入预产期后，就能查看当前孕周并录入产检。')">预产期说明</button>
            <button class="button-primary" type="button" @click="changeView('pregnancy')">设置预产期</button>
          </section>
          <section v-if="nextVisit" class="appointment-card panel">
            <h2>下次产检</h2>
            <p><strong>{{ nextVisit.next_visit_date }} {{ displayTime(nextVisit.next_visit_time) }}</strong></p>
            <p v-if="nextVisit.hospital">{{ nextVisit.hospital }}</p>
          </section>
        </div>

        <RecordingShortcuts :today="snapshot.today" @navigate="changeView" @failed="fail" />

        <section class="checkup-section">
          <div class="section-heading">
            <h2>产检记录</h2>
            <div class="settings-controls">
              <button class="button-text" type="button" :disabled="busy" @click="changeView('trends')">指标趋势</button>
              <button v-if="pregnancy" class="button-primary" type="button" :disabled="busy" @click="openCheckup()">录入产检</button>
            </div>
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
  <TipHost />
</template>
