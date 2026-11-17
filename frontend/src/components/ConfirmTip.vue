<script setup>
import { onMounted, onUnmounted, ref } from 'vue'

const props = defineProps({
  message: { type: String, required: true },
  action: { type: String, required: true },
  busy: Boolean,
})
const emit = defineEmits(['cancel', 'confirm'])
const cancelButton = ref(null)
let trigger

onMounted(() => {
  trigger = document.activeElement
  cancelButton.value?.focus()
})
onUnmounted(() => {
  if (trigger?.isConnected && document.activeElement === document.body) trigger.focus()
})
</script>

<template>
  <Teleport to="#app-confirm-tip">
    <section class="tip-banner tip-confirm" role="group" aria-label="操作确认" data-kind="error"
      @keydown.esc.stop="!props.busy && emit('cancel')">
      <p>{{ message }}</p>
      <div class="tip-actions">
        <button ref="cancelButton" type="button" :disabled="busy" @click="emit('cancel')">取消</button>
        <button class="tip-danger" type="button" :disabled="busy" @click="emit('confirm')">{{ action }}</button>
      </div>
    </section>
  </Teleport>
</template>
