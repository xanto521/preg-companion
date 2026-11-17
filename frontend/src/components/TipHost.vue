<script setup>
import { activeTip, dismissTip } from '../tips'
</script>

<template>
  <Teleport to="body">
    <div class="tip-stack">
      <div v-if="activeTip" class="tip-banner" :data-kind="activeTip.kind">
        <p :role="activeTip.kind === 'error' ? 'alert' : 'status'">{{ activeTip.message }}</p>
        <button class="tip-close" type="button" aria-label="关闭提示" @click="dismissTip">×</button>
      </div>
      <div id="app-confirm-tip"></div>
    </div>
  </Teleport>
</template>
