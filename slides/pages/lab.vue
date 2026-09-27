<!--
  /#/lab: the scene workbench.

    /#/lab                                  list of scenes
    /#/lab?scene=thesis                    scrubber, cue buttons, play
    /#/lab?scene=thesis&sheet=1&cols=4     contact sheet at every cue
    /#/lab?scene=thesis&times=0,1.5,3      contact sheet at chosen times

  "Look before rendering": a contact sheet catches the ghost element, the label
  on top of the object and the camera bug that are invisible in code.
-->
<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { scenes } from '../scenes'
import { H, W, type FitBox } from '../lib/scene/kit'
import { renderScene, stageAt } from '../lib/scene/render'

// Plain hash parsing: vue-router is Slidev's internal dependency, not ours.
const hashQuery = () => new URLSearchParams(window.location.hash.split('?')[1] ?? '')
const query = ref(hashQuery())
window.addEventListener('hashchange', () => { query.value = hashQuery() })
const q = (k: string) => query.value.get(k) ?? undefined

const name = computed(() => q('scene') ?? '')
const variant = computed(() => q('v'))
const def = computed(() => scenes[name.value])
const cues = computed(() => def.value?.cues ?? [0])
const end = computed(() => cues.value[cues.value.length - 1] + 0.5)

const times = computed<number[] | null>(() => {
  if (q('times')) return q('times')!.split(',').map(Number)
  if (q('sheet')) {
    // every cue, plus the midpoint of each segment
    const out: number[] = []
    cues.value.forEach((c, i) => {
      const prev = i === 0 ? 0 : cues.value[i - 1]
      out.push((prev + c) / 2, c)
    })
    return out
  }
  return null
})
const cols = computed(() => Number(q('cols') ?? 4))

const t = ref(0)
const playing = ref(false)
const main = ref<HTMLCanvasElement>()
const cells = ref<HTMLCanvasElement[]>([])

function paint() {
  if (main.value) renderScene(main.value, name.value, t.value, stageAt(name.value, t.value), undefined, variant.value)
}
function paintSheet() {
  times.value?.forEach((tt, i) => {
    const c = cells.value[i]
    if (c) renderScene(c, name.value, tt, stageAt(name.value, tt), undefined, variant.value)
  })
}

let last = 0
function loop(now: number) {
  if (!playing.value) return
  const dt = last ? (now - last) / 1000 : 0
  last = now
  t.value = Math.min(end.value, t.value + dt)
  if (t.value >= end.value) playing.value = false
  requestAnimationFrame(loop)
}
function play() {
  if (t.value >= end.value - 0.01) t.value = 0
  playing.value = true
  last = 0
  requestAnimationFrame(loop)
}

watch([t, name], paint)
watch([times, name], async () => {
  await nextTick()
  paintSheet()
})
onMounted(async () => {
  await document.fonts.ready
  await Promise.all([
    document.fonts.load("700 40px 'Unbounded Variable'"),
    document.fonts.load("600 40px 'Instrument Sans Variable'"),
    document.fonts.load("500 40px 'Geist Mono Variable'"),
  ]).catch(() => {})
  paint()
  paintSheet()
  if (q('fit')) fitReport()
  ;(window as unknown as { __labReady: boolean }).__labReady = true
})

/**
 * ?fit=1: render every scene at every cue with the kit's text probe on and
X * top and bottom) or overlapping other text by more than 6 px on both axes.
 */
function fitReport() {
  const g = globalThis as unknown as { __fit?: FitBox[]; __fitReport?: string[] }
  const c = document.createElement('canvas')
  c.width = W
  c.height = H
  const out: string[] = []
  for (const [n, d] of Object.entries(scenes)) {
    d.cues.forEach((cue, i) => {
      g.__fit = []
      renderScene(c, n, cue, i)
      const boxes = g.__fit
      g.__fit = undefined
      for (const b of boxes) {
        if (b.x0 < 60 || b.x1 > W - 60 || b.y0 < 30 || b.y1 > H - 30) out.push(`${n} cue ${i}: "${b.s}" leaves the safe area`)
      }
      for (let a = 0; a < boxes.length; a++) {
        for (let b = a + 1; b < boxes.length; b++) {
          const A = boxes[a]
          const B = boxes[b]
          const ox = Math.min(A.x1, B.x1) - Math.max(A.x0, B.x0)
          const oy = Math.min(A.y1, B.y1) - Math.max(A.y0, B.y0)
          // overlapping, or touching when they are not neighbouring words of one line
          if ((ox > 6 && oy > 6) || (b !== a + 1 && ox > -3 && oy > 4)) out.push(`${n} cue ${i}: "${A.s}" overlaps or touches "${B.s}"`)
        }
      }
    })
  }
  g.__fitReport = out
}

function setQ(patch: Record<string, string | undefined>) {
  const next = new URLSearchParams(query.value)
  for (const [k, v] of Object.entries(patch)) v === undefined ? next.delete(k) : next.set(k, v)
  window.location.hash = `#/lab?${next}`
}
</script>

<template>
  <div class="lab">
    <template v-if="!def">
      <h1>Scenes</h1>
      <ul>
        <li v-for="n in Object.keys(scenes)" :key="n">
          <a href="#" @click.prevent="setQ({ scene: n })">{{ n }}</a>
          <span class="lab__m">: {{ scenes[n].cues.length - 1 }} clicks</span>
        </li>
      </ul>
    </template>

    <div v-else-if="times" class="lab__sheet" :style="{ gridTemplateColumns: `repeat(${cols}, 1fr)` }">
      <figure v-for="(tt, i) in times" :key="i">
        <canvas :ref="(c) => { if (c) cells[i] = c as HTMLCanvasElement }" :width="960" :height="540" />
        <figcaption>t={{ tt.toFixed(2) }} · stage {{ stageAt(name, tt) }}</figcaption>
      </figure>
    </div>

    <template v-else>
      <canvas ref="main" class="lab__main" :width="W" :height="H" />
      <div class="lab__bar">
        <button @click="playing ? (playing = false) : play()">{{ playing ? 'pause' : 'play' }}</button>
        <input v-model.number="t" type="range" min="0" :max="end" step="0.01">
        <span class="lab__m">{{ t.toFixed(2) }}s · stage {{ stageAt(name, t) }}</span>
        <button v-for="(c, i) in cues" :key="i" @click="t = c">{{ i }}</button>
        <a href="#" @click.prevent="setQ({ scene: undefined })">all</a>
      </div>
    </template>
  </div>
</template>

<style scoped>
.lab { background: #070707; color: #E6E6E4; min-height: 100vh; padding: 16px; font-family: 'Geist Mono Variable', monospace; font-size: 13px; overflow: auto; height: 100vh; }
.lab a { color: #6F9BFF; }
.lab__main { width: 100%; max-width: 1280px; aspect-ratio: 16 / 9; display: block; outline: 1px solid #2E2E2E; }
.lab__bar { display: flex; gap: 8px; align-items: center; margin-top: 10px; flex-wrap: wrap; }
.lab__bar input { flex: 1; min-width: 200px; }
.lab__bar button { background: #121212; color: #E6E6E4; border: 1px solid #2E2E2E; padding: 4px 10px; border-radius: 6px; cursor: pointer; }
.lab__m { color: #8C8C89; }
.lab__sheet { display: grid; gap: 8px; }
.lab__sheet figure { margin: 0; }
.lab__sheet canvas { width: 100%; aspect-ratio: 16 / 9; display: block; outline: 1px solid #2E2E2E; }
.lab__sheet figcaption { color: #8C8C89; margin-top: 2px; }
</style>
