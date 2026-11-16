<script setup>
const day = defineModel({ type: String, required: true })
defineProps({ busy: Boolean })

function move(amount) {
  const date = new Date(day.value + 'T00:00:00Z')
  date.setUTCDate(date.getUTCDate() + amount)
  day.value = date.toISOString().slice(0, 10)
}
</script>

<template>
  <div class="day-picker">
    <button class="button-secondary" type="button" :disabled="busy || day <= '0001-01-01'" @click="move(-1)">前一天</button>
    <label class="field"><span class="visually-hidden">记录日期</span><input type="date"
      :value="day" :disabled="busy" min="0001-01-01" max="9999-12-31"
      @change="$event.target.validity.valid && $event.target.value ? day = $event.target.value : $event.target.value = day"></label>
    <button class="button-secondary" type="button" :disabled="busy || day >= '9999-12-31'" @click="move(1)">后一天</button>
  </div>
</template>
