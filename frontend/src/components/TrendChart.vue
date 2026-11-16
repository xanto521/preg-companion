<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { gestationLabel } from './pregnancy'

const props = defineProps({ series: { type: Object, required: true }, axis: { type: String, required: true } })
const canvas = ref(null)
const palette = ref(null)
const selected = ref(-1)
const formatter = new Intl.NumberFormat('zh-CN', { maximumSignificantDigits: 8 })
const tickFormatter = new Intl.NumberFormat('zh-CN', { notation: 'compact', maximumFractionDigits: 2 })
let plotted = []
let observer
let themeObserver
let media
let resizePending = 0

const values = computed(() => props.series.points.map((point, index) => ({
  ...point, index,
  x: props.axis === 'gestation' ? point.ga_days : Date.parse(point.day) / 86400000,
})).filter(point => point.x != null).sort((a, b) => a.x - b.x || a.index - b.index))
const recent = computed(() => props.series.points.map((point, index) => ({ ...point, index })).reverse())
const current = computed(() => props.series.points[selected.value])
const bounds = computed(() => [props.series.metric.ref_low, props.series.metric.ref_high])

function outside(value) {
  const [low, high] = bounds.value
  return (low != null && value < low) || (high != null && value > high)
}

function tickLabel(x) {
  if (props.axis === 'date') {
    const label = new Date(x * 86400000).toISOString().slice(0, 10)
    return label.slice(5)
  }
  return x < 0 ? x + '天' : Math.floor(x / 7) + '周' + (x % 7 ? '+' + x % 7 : '')
}

function draw() {
  const node = canvas.value
  if (!node || !values.value.length) return
  const { width, height } = node.getBoundingClientRect()
  if (width < 10 || height < 10) return
  const ratio = Math.min(window.devicePixelRatio || 1, 3)
  node.width = Math.round(width * ratio)
  node.height = Math.round(height * ratio)
  const context = node.getContext('2d')
  if (!context) return
  context.scale(ratio, ratio)
  const colors = Object.fromEntries(Array.from(palette.value.children, item => [
    item.dataset.color, getComputedStyle(item).color,
  ]))

  const left = 48
  const right = width - 24
  const top = 14
  const bottom = height - 34
  const points = values.value
  const minX = points[0].x
  const maxX = points.at(-1).x
  const [refLow, refHigh] = bounds.value
  const range = points.map(point => point.value).concat(bounds.value.filter(value => value != null))
  const scale = range.reduce((largest, value) => Math.max(largest, Math.abs(value)), 1)
  let low = 1
  let high = -1
  for (const value of range) {
    low = Math.min(low, value / scale)
    high = Math.max(high, value / scale)
  }
  const padding = (high - low) * 0.12 || 0.08
  low -= padding
  high += padding
  const xAt = value => minX === maxX ? (left + right) / 2 : left + (value - minX) / (maxX - minX) * (right - left)
  const yAt = value => bottom - (value - low) / (high - low) * (bottom - top)

  if (refLow != null || refHigh != null) {
    const bandTop = refHigh == null ? top : yAt(refHigh / scale)
    const bandBottom = refLow == null ? bottom : yAt(refLow / scale)
    context.fillStyle = colors.band
    context.fillRect(left, bandTop, right - left, Math.max(2, bandBottom - bandTop))
  }

  context.font = '12px system-ui, sans-serif'
  context.textAlign = 'right'
  context.textBaseline = 'middle'
  for (let step = 0; step <= 4; step++) {
    const value = low + (high - low) * step / 4
    const y = yAt(value)
    context.strokeStyle = colors.grid
    context.lineWidth = 1
    context.beginPath()
    context.moveTo(left, y)
    context.lineTo(right, y)
    context.stroke()
    context.fillStyle = colors.text
    const original = value * scale
    context.fillText(Number.isFinite(original) ? tickFormatter.format(original) : '', left - 7, y, 38)
  }
  const count = width < 345 ? 3 : 4
  const ticks = new Set(Array.from({ length: count }, (_, index) => Math.round(minX + (maxX - minX) * index / (count - 1))))
  context.textAlign = 'center'
  for (const x of ticks) context.fillText(tickLabel(x), xAt(x), bottom + 17)

  plotted = points.map(point => ({ index: point.index, x: xAt(point.x), y: yAt(point.value / scale) }))
  context.strokeStyle = colors.line
  context.lineWidth = 2
  context.beginPath()
  plotted.forEach((point, index) => index ? context.lineTo(point.x, point.y) : context.moveTo(point.x, point.y))
  context.stroke()
  for (const point of plotted) {
    const emphasized = point.index === selected.value
    const alert = outside(props.series.points[point.index].value)
    const radius = emphasized ? 6 : 4
    context.fillStyle = alert ? colors.notice : colors.line
    context.beginPath()
    if (alert) {
      context.moveTo(point.x, point.y - radius)
      context.lineTo(point.x + radius, point.y)
      context.lineTo(point.x, point.y + radius)
      context.lineTo(point.x - radius, point.y)
      context.closePath()
    } else {
      context.arc(point.x, point.y, radius, 0, Math.PI * 2)
    }
    context.fill()
  }
}

function redraw() {
  cancelAnimationFrame(resizePending)
  resizePending = requestAnimationFrame(draw)
}

function pick(event) {
  const bounds = canvas.value.getBoundingClientRect()
  let nearest = null
  let distance = Infinity
  for (const point of plotted) {
    const candidate = Math.hypot(point.x - (event.clientX - bounds.left), point.y - (event.clientY - bounds.top))
    if (candidate < distance) {
      nearest = point
      distance = candidate
    }
  }
  if (nearest) selected.value = nearest.index
}

watch([() => props.series, () => props.axis], () => {
  selected.value = values.value.at(-1)?.index ?? -1
  redraw()
}, { immediate: true, flush: 'post' })
watch(selected, redraw)
watch(canvas, (node, previous) => {
  if (previous) observer?.unobserve(previous)
  if (node) observer?.observe(node)
  redraw()
})
onMounted(() => {
  observer = new ResizeObserver(redraw)
  if (canvas.value) observer.observe(canvas.value)
  media = window.matchMedia('(prefers-color-scheme: dark)')
  media.addEventListener('change', redraw)
  themeObserver = new MutationObserver(redraw)
  themeObserver.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] })
  redraw()
})
onUnmounted(() => {
  cancelAnimationFrame(resizePending)
  observer?.disconnect()
  themeObserver?.disconnect()
  media?.removeEventListener('change', redraw)
})
</script>

<template>
  <div class="trend-body">
    <div ref="palette" class="trend-palette" aria-hidden="true">
      <span data-color="text" class="trend-text-color"></span><span data-color="grid" class="trend-grid-color"></span>
      <span data-color="line" class="trend-line-color"></span><span data-color="band" class="trend-band-color"></span>
      <span data-color="notice" class="trend-notice-color"></span>
    </div>
    <template v-if="values.length">
      <canvas ref="canvas" role="img" :aria-label="`${series.metric.name}按${axis === 'gestation' ? '孕周' : '日期'}排列的趋势图，详细数据见下方`" @click="pick"></canvas>
      <p v-if="current" class="trend-point-detail" aria-live="polite">
        <strong>{{ formatter.format(current.value) }} {{ series.metric.unit }}</strong>
        <span>{{ current.day }} · {{ gestationLabel(current.ga_days) }}</span>
        <span v-if="outside(current.value)" class="trend-attention">需关注 · 超出填写的参考范围</span>
      </p>
    </template>
    <p v-else class="trend-hint">{{ recent.length ? '这些记录还没有保存孕周，可切到日期查看。' : '还没有这个指标的记录。' }}</p>
    <p v-if="bounds[0] != null || bounds[1] != null" class="trend-hint">
      参考范围 {{ bounds[0] != null && bounds[1] != null ? `${bounds[0]}–${bounds[1]}` : bounds[0] != null ? `≥ ${bounds[0]}` : `≤ ${bounds[1]}` }}
      {{ series.metric.unit }}
    </p>
    <ol v-if="recent.length" class="trend-readings" aria-label="最近测量记录">
      <li v-for="point in recent" :key="point.index">
        <button type="button" :aria-pressed="selected === point.index" @click="selected = point.index">
          <span>{{ point.day }} <small>{{ gestationLabel(point.ga_days) }}</small></span>
          <strong>{{ formatter.format(point.value) }} {{ series.metric.unit }}</strong>
          <small v-if="outside(point.value)" class="trend-attention">需关注</small>
        </button>
      </li>
    </ol>
  </div>
</template>
