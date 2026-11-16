<script setup>
import { onMounted, ref } from 'vue'

const serviceStatus = ref('checking')

async function checkService() {
  serviceStatus.value = 'checking'

  try {
    const response = await fetch('/api/health', {
      cache: 'no-store',
      signal: AbortSignal.timeout(5000),
    })
    const health = response.ok && await response.json()
    serviceStatus.value = health?.status === 'ok' ? 'ready' : 'unavailable'
  } catch {
    serviceStatus.value = 'unavailable'
  }
}

onMounted(checkService)
</script>

<template>
  <main class="shell">
    <h1>孕期陪伴</h1>
    <p>产检和每日记录功能正在开发。</p>
    <footer class="connection">
      <div class="connection-status" :data-state="serviceStatus" role="status">
        <span class="status-dot" aria-hidden="true"></span>
        <span v-if="serviceStatus === 'checking'">正在连接服务…</span>
        <span v-else-if="serviceStatus === 'ready'">服务已连接</span>
        <span v-else>暂时无法连接服务</span>
      </div>
      <button v-if="serviceStatus === 'unavailable'" class="button-primary" type="button" @click="checkService">
        重试
      </button>
    </footer>
  </main>
</template>
