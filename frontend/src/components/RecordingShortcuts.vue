<script setup>
import { onMounted, ref } from 'vue'
import { api } from '../api/recorder'

const props = defineProps({ today: { type: String, required: true } })
const emit = defineEmits(['navigate', 'failed'])
const tasks = ref(null)

onMounted(async () => {
  try {
    const [plans, questions] = await Promise.all([
      api(`/supplements?day=${props.today}`), api('/questions'),
    ])
    const scheduled = plans.filter(item => item.scheduled)
    tasks.value = {
      taken: scheduled.filter(item => item.taken).length,
      planned: scheduled.length,
      questions: questions.filter(item => item.status === 'open').length,
    }
  } catch (problem) {
    if (problem.status === 401) emit('failed', problem)
  }
})
</script>

<template>
  <section class="checkup-section fields" aria-label="今日待办与快捷记录">
    <div class="panel quick-tasks">
      <h2>今日待办</h2>
      <div class="settings-controls">
        <button class="button-text" type="button" @click="emit('navigate', 'supplements')">
          {{ tasks ? `补剂已打卡 ${tasks.taken}/${tasks.planned}` : '补剂打卡' }}
        </button>
        <button class="button-text" type="button" @click="emit('navigate', 'questions')">
          {{ tasks ? `待问医生 ${tasks.questions} 项` : '待问医生' }}
        </button>
      </div>
    </div>
    <div class="quick-records">
      <button class="button-secondary" type="button" @click="emit('navigate', 'daily')">饮食</button>
      <button class="button-secondary" type="button" @click="emit('navigate', 'symptoms')">症状</button>
      <button class="button-secondary" type="button" @click="emit('navigate', 'supplements')">补剂</button>
      <button class="button-secondary" type="button" @click="emit('navigate', 'notes')">备注</button>
    </div>
  </section>
</template>
