/**
 * System primitives for a banking service, drawn in the deck's colour grammar.
 * They replace the VLA deck's robot helpers. Every function is stateless:
 * pass the progress (k, 0..1) and it draws that frame.
 *
 *   tone('blue')    the model: understanding, extraction
 *   tone('yellow')  deterministic code: rules, states, verified actions
 *   tone('red')     risk: refusal, escalation, a blocked injection
 *   tone('paper')   data: customers, records, documents
 */
import { C, type Kit } from './kit'
import { clamp, outBack, outCubic, outExpo } from './math'
import { KIND_LABEL, type Metric } from '../metrics'

export type Tone = 'blue' | 'yellow' | 'red' | 'paper'

export const tone = (t: Tone) =>
  ({
    blue: { main: C.blue, text: C.blueText, deep: C.blueDeep },
    yellow: { main: C.yellow, text: C.yellow, deep: C.yellowDeep },
    red: { main: C.red, text: C.redText, deep: C.redDeep },
    paper: { main: C.paper, text: C.paper, deep: C.bg2 },
  })[t]

/** Point at fraction u (0..1) of the length of a polyline. */
export function along(pts: readonly { x: number; y: number }[], u: number) {
  const lens = [0]
  for (let i = 1; i < pts.length; i++) lens.push(lens[i - 1] + Math.hypot(pts[i].x - pts[i - 1].x, pts[i].y - pts[i - 1].y))
  const L = lens[lens.length - 1] * clamp(u)
  for (let i = 1; i < pts.length; i++) {
    if (lens[i] >= L) {
      const f = (L - lens[i - 1]) / (lens[i] - lens[i - 1] || 1)
      return { x: pts[i - 1].x + (pts[i].x - pts[i - 1].x) * f, y: pts[i - 1].y + (pts[i].y - pts[i - 1].y) * f }
    }
  }
  return pts[pts.length - 1]
}

/**
 * A system component: a deep-tinted block with an accent bar on its left edge,
 * a label and an optional mono sub-label. k is its arrival (fade and rise).
 */
export function node(
  K: Kit, x: number, y: number, w: number, h: number,
  o: { label: string; sub?: string; tone: Tone; k?: number; size?: number; bar?: boolean; filled?: boolean },
) {
  const k = o.k ?? 1
  if (k <= 0) return
  const c = tone(o.tone)
  // filled: the accent itself is the block, with ink text (never red: ink on red is large-only)
  const fg = o.filled ? C.bg : C.paper
  const sub = o.filled ? (o.tone === 'blue' ? C.bg : C.inkDim) : c.text
  K.fade(clamp(k * 2), () => {
    const dy = (1 - outExpo(k)) * 24
    K.fillRR(x, y + dy, w, h, 10, o.filled ? c.main : c.deep)
    if (o.bar !== false && !o.filled) K.fillRR(x, y + dy, 6, h, 3, c.main)
    const size = o.size ?? 30
    const cy = y + dy + h / 2
    K.text(o.label, x + 30, o.sub ? cy - 6 : cy, { size, weight: 600, color: fg, base: o.sub ? 'alphabetic' : 'middle' })
    if (o.sub) K.text(o.sub, x + 30, cy + 30, { size: 22, weight: 500, fam: 'mono', color: sub })
  })
}

/** A filled tab with ink text: the loudest label the deck has. Returns its width. */
export const tab = (K: Kit, label: string, x: number, y: number, o: { tone: Tone; k?: number; size?: number; align?: 'left' | 'center' } = { tone: 'yellow' }) =>
  K.chip(label, x, y, { bg: tone(o.tone).main, fg: C.bg, k: o.k ?? 1, size: o.size ?? 24, weight: 700, align: o.align })

/** A tinted chip: accent text on its deep tint. Returns its width. */
export const tag = (K: Kit, label: string, x: number, y: number, o: { tone: Tone; k?: number; size?: number; align?: 'left' | 'center' } = { tone: 'blue' }) =>
  K.chip(label, x, y, { bg: tone(o.tone).deep, fg: tone(o.tone).text, k: o.k ?? 1, size: o.size ?? 26, align: o.align })

/** A customer or system message. Returns the bubble height. */
export function bubble(
  K: Kit, s: string, x: number, y: number,
  o: { maxW?: number; k?: number; typed?: number; tone?: Tone; size?: number; align?: 'left' | 'right'; label?: string },
) {
  const size = o.size ?? 36
  const maxW = o.maxW ?? 900
  const lines = K.wrap(s, maxW - 64, size, 500, 'sans')
  const w = Math.min(maxW, Math.max(...lines.map((l) => K.measure(l, size, 500, 'sans'))) + 64)
  const h = lines.length * size * 1.3 + 48
  const k = o.k ?? 1
  if (k <= 0) return h
  const x0 = o.align === 'right' ? x - w : x
  const c = tone(o.tone ?? 'paper')
  K.fade(clamp(k * 2), () => {
    const dy = (1 - outExpo(k)) * 30
    K.fillRR(x0, y + dy, w, h, 22, o.tone && o.tone !== 'paper' ? c.deep : C.bg2)
    K.strokeRR(x0, y + dy, w, h, 22, o.tone === 'paper' || !o.tone ? C.faint : c.main, 2)
    if (o.label) K.label(o.label, x0 + 4, y + dy - 18, { size: 22, color: C.mute })
    let left = o.typed === undefined ? Infinity : Math.round(clamp(o.typed) * s.length)
    lines.forEach((ln, i) => {
      const shown = ln.slice(0, Math.max(0, left))
      left -= ln.length + 1
      K.text(shown, x0 + 32, y + dy + 24 + size * 0.95 + i * size * 1.3, { size, weight: 500, color: C.paper })
    })
  })
  return h
}

/** A check mark drawn on over k. */
export function check(K: Kit, x: number, y: number, s: number, k: number, color: string = C.yellow, lw = 6) {
  if (k <= 0) return
  K.trace([{ x: x - s * 0.5, y }, { x: x - s * 0.15, y: y + s * 0.35 }, { x: x + s * 0.55, y: y - s * 0.4 }], outCubic(k), { color, lw })
}

/** A cross drawn on over k (two strokes). */
export function cross(K: Kit, x: number, y: number, s: number, k: number, color: string = C.red, lw = 6) {
  if (k <= 0) return
  const h = s / 2
  K.trace([{ x: x - h, y: y - h }, { x: x + h, y: y + h }], outCubic(clamp(k * 2)), { color, lw })
  K.trace([{ x: x + h, y: y - h }, { x: x - h, y: y + h }], outCubic(clamp(k * 2 - 1)), { color, lw })
}

/** Regular hexagon (pointy sides left and right), stroke drawn on over k. */
export function hex(K: Kit, cx: number, cy: number, r: number, o: { k?: number; stroke?: string; fill?: string; lw?: number } = {}) {
  const pts = Array.from({ length: 7 }, (_, i) => ({ x: cx + r * Math.cos((Math.PI / 3) * i), y: cy + r * Math.sin((Math.PI / 3) * i) }))
  const k = o.k ?? 1
  if (k <= 0) return
  if (o.fill) {
    K.fade(clamp(k * 1.5 - 0.5), () => {
      const ctx = K.ctx
      ctx.beginPath()
      pts.forEach((p, i) => (i ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y)))
      ctx.closePath()
      ctx.fillStyle = o.fill!
      ctx.fill()
    })
  }
  if (o.stroke) K.trace(pts, k, { color: o.stroke, lw: o.lw ?? 3 })
}

/**
 * The citation line, bottom-left: what kind of number it is and where it came
 * from, e.g. "offline measurement  |  docs/analysis/workflow-evidence.md".
 * `extra` appends a note such as a sample size.
 */
export function source(K: Kit, m: Metric, a = 1, extra?: string, color?: string) {
  K.cite(`${KIND_LABEL[m.kind]}  |  ${m.source}${extra ? `  |  ${extra}` : ''}`, a, color)
}

/**
 * The evaluation dimensions a slide answers, top-right in the caption voice,
 * so a judge can map the slide to the organizers' criteria. One per slide,
 * drawn at rest; `color` follows the ground (mute on ink, inkMute on paper,
 * inkDim on yellow).
 */
export function dims(K: Kit, s: string, a = 1, color: string = C.mute) {
  K.text(s, 1920 - 120, 72, { size: 22, weight: 500, fam: 'mono', color, align: 'right', alpha: a })
}

/** A metric value, or a visible "pending" placeholder when phase 14 has not landed. Returns width. */
export function metricValue(
  K: Kit, m: Metric, x: number, y: number,
  o: { size?: number; color?: string; align?: CanvasTextAlign; k?: number; fam?: 'display' | 'sans' | 'mono' } = {},
) {
  const size = o.size ?? 64
  const k = o.k ?? 1
  if (m.pending) {
    const w = Math.max(size * 3.2, 200)
    const h = size * 1.05
    const x0 = o.align === 'center' ? x - w / 2 : o.align === 'right' ? x - w : x
    K.fade(k, () => {
      K.ctx.save()
      K.ctx.setLineDash([10, 8])
      K.strokeRR(x0, y - h * 0.82, w, h, 8, C.mute, 2)
      K.ctx.restore()
      K.text('pending', x0 + w / 2, y - h * 0.3, { size: Math.max(22, size * 0.36), weight: 500, fam: 'mono', color: C.mute, align: 'center', base: 'middle' })
    })
    return w
  }
  K.fade(k, () => K.text(m.text, x, y + (1 - outBack(k)) * 12, { size, weight: 700, fam: o.fam ?? 'display', color: o.color ?? C.paper, align: o.align ?? 'left', ls: -0.02 }))
  return K.measure(m.text, size, 700, o.fam ?? 'display', -0.02)
}
