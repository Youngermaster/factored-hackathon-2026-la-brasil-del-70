/**
 * Canvas drawing kit shared by every scene.
 *
 * Scenes draw in a fixed 1920 × 1080 logical space; <Scene> scales the backing
 * store to the screen. Nothing here keeps state between frames: every helper
 * takes the current time (or a progress value) and draws.
 *
 * Adapted from the VLA-introduction-slides scene kit (Apache-2.0, same author).
 *
 * Colour semantics are the deck's, never swapped (styles/tokens.css mirrors
 * these values; pnpm check:content fails when the two drift apart):
 *   BLUE    the language model and understanding: intents, extraction, tokens
 *   YELLOW  deterministic code deciding and acting: rules, states, verified tools
 *   RED     risk, refusal, escalation, a blocked injection
 *   PAPER   data, customers, documents, plain text
 * Body-size text in an accent uses the `*Text` tint; the saturated value is
 * for fills, strokes and large type (see lib/scene/contrast.ts).
 */
import { alpha, clamp, outBack, outCubic, outExpo, seg } from './math'

export const W = 1920
export const H = 1080
/** The left and right content margin; titles, citations and body align to it. */
export const MX = 120

export const C = {
  bg: '#070707',
  bg2: '#121212',
  rail: '#1F1F1F',
  faint: '#2E2E2E',
  paper: '#E6E6E4',
  dim: '#B8B8B5',
  mute: '#8C8C89',
  blue: '#3772FF',
  blueText: '#6F9BFF',
  blueDeep: '#0E1A3A',
  yellow: '#FDC840',
  yellowDeep: '#2B2208',
  red: '#E12B37',
  redText: '#F0616A',
  redDeep: '#2E0B0E',
} as const
export type Color = (typeof C)[keyof typeof C]

export const FONT = {
  display: "'Unbounded Variable', 'Arial Black', sans-serif",
  sans: "'Instrument Sans Variable', 'Helvetica Neue', Arial, sans-serif",
  mono: "'Geist Mono Variable', ui-monospace, Menlo, monospace",
} as const
export type Fam = keyof typeof FONT

export interface TextOpts {
  size?: number
  weight?: number
  fam?: Fam
  color?: string
  align?: CanvasTextAlign
  base?: CanvasTextBaseline
  alpha?: number
  /** letter spacing in em */
  ls?: number
}

/** Canvas `filter` is Chromium/Firefox; Safari ignores it. Blur is a garnish, never load-bearing. */
const canFilter = typeof CanvasRenderingContext2D !== 'undefined' && 'filter' in CanvasRenderingContext2D.prototype

/**
 * Fit probe (scripts/check-fit.mjs): when `globalThis.__fit` is an array, every
 * text draw records its box in logical 1920 x 1080 units, so the check can
 * flag text outside the safe area or on top of other text at each cue.
 */
export interface FitBox { s: string; x0: number; y0: number; x1: number; y1: number; a: number }
function probe(ctx: CanvasRenderingContext2D, s: string, x: number, y: number) {
  const sink = (globalThis as { __fit?: FitBox[] }).__fit
  if (!sink || !s.trim() || ctx.globalAlpha < 0.5) return
  const m = ctx.measureText(s)
  const T = ctx.getTransform()
  const k = ctx.canvas.width / W
  const pt = (px: number, py: number) => ({ x: (T.a * px + T.c * py + T.e) / k, y: (T.b * px + T.d * py + T.f) / k })
  const p0 = pt(x - m.actualBoundingBoxLeft, y - m.actualBoundingBoxAscent)
  const p1 = pt(x + m.actualBoundingBoxRight, y + m.actualBoundingBoxDescent)
  sink.push({ s, x0: Math.min(p0.x, p1.x), y0: Math.min(p0.y, p1.y), x1: Math.max(p0.x, p1.x), y1: Math.max(p0.y, p1.y), a: ctx.globalAlpha })
}

export function makeKit(ctx: CanvasRenderingContext2D) {
  const setFont = (size: number, weight = 600, fam: Fam = 'sans', ls = 0) => {
    ctx.font = `${weight} ${size}px ${FONT[fam]}`
    if ('letterSpacing' in ctx) (ctx as CanvasRenderingContext2D & { letterSpacing: string }).letterSpacing = `${ls * size}px`
  }

  const measure = (s: string, size: number, weight = 600, fam: Fam = 'sans', ls = 0) => {
    setFont(size, weight, fam, ls)
    return ctx.measureText(s).width
  }

  const text = (s: string, x: number, y: number, o: TextOpts = {}) => {
    const { size = 32, weight = 600, fam = 'sans', color = C.paper, align = 'left', base = 'alphabetic', ls = 0 } = o
    ctx.save()
    if (o.alpha !== undefined) ctx.globalAlpha *= clamp(o.alpha)
    setFont(size, weight, fam, ls)
    ctx.fillStyle = color
    ctx.textAlign = align
    ctx.textBaseline = base
    ctx.fillText(s, x, y)
    probe(ctx, s, x, y)
    ctx.restore()
  }

  /** Greedy word wrap. Respects explicit \n. */
  const wrap = (s: string, maxW: number, size: number, weight = 600, fam: Fam = 'sans', ls = 0) => {
    setFont(size, weight, fam, ls)
    const out: string[] = []
    for (const para of s.split('\n')) {
      let line = ''
      for (const w of para.split(/\s+/).filter(Boolean)) {
        const next = line ? `${line} ${w}` : w
        if (ctx.measureText(next.replace(/\*/g, '')).width > maxW && line) {
          out.push(line)
          line = w
        }
        else line = next
      }
      out.push(line)
    }
    return out
  }

  /**
   * Kinetic words: the caption language from the motion playbook: each word
   * blur-rises ~40 ms after the previous one; words wrapped in *asterisks* take
   * the accent colour (multi-word accents run to the closing asterisk).
   * Returns the block height so callers can stack blocks.
   */
  const words = (
    s: string,
    x: number,
    y: number,
    o: TextOpts & {
      t: number
      t0: number
      stagger?: number
      dur?: number
      maxW?: number
      lh?: number
      accent?: string
      /** time at which the block leaves (words lift out, same stagger) */
      tout?: number
    },
  ) => {
    const { size = 64, weight = 700, fam = 'display', color = C.paper, accent = C.yellow, stagger = 0.04, dur = 0.5, maxW = 1600, lh = 1.12, align = 'left', ls = -0.02 } = o
    const lines = wrap(s, maxW, size, weight, fam, ls)
    setFont(size, weight, fam, ls)
    const space = ctx.measureText(' ').width
    let open = false
    let wi = 0
    lines.forEach((line, li) => {
      const ws = line.split(' ').filter(Boolean)
      const clean = ws.map((w) => w.replace(/\*/g, ''))
      const total = clean.reduce((a, w) => a + ctx.measureText(w).width, 0) + space * (ws.length - 1)
      let cx = align === 'center' ? x - total / 2 : align === 'right' ? x - total : x
      ws.forEach((w, i) => {
        const starts = w.startsWith('*')
        const on = open || starts
        const closes = (starts ? w.slice(1) : w).includes('*')
        open = on && !closes
        const k = outExpo(seg(o.t, o.t0 + wi * stagger, o.t0 + wi * stagger + dur))
        const out = o.tout !== undefined ? outCubic(seg(o.t, o.tout + wi * 0.02, o.tout + wi * 0.02 + 0.3)) : 0
        const vis = Math.min(clamp(k * 3), 1 - out)
        const ww = ctx.measureText(clean[i]).width
        if (vis > 0) {
          ctx.save()
          ctx.globalAlpha *= vis
          if (canFilter && (k < 0.98 || out > 0.02)) ctx.filter = `blur(${((1 - k) * 12 + out * 10).toFixed(1)}px)`
          setFont(size, weight, fam, ls)
          ctx.fillStyle = on ? accent : color
          ctx.textAlign = 'left'
          ctx.textBaseline = 'alphabetic'
          ctx.fillText(clean[i], cx, y + li * size * lh + (1 - k) * size * 0.42 - out * size * 0.3)
          probe(ctx, clean[i], cx, y + li * size * lh + (1 - k) * size * 0.42 - out * size * 0.3)
          ctx.restore()
        }
        cx += ww + space
        wi++
      })
    })
    return lines.length * size * lh
  }

  /** Letters rising through a mask line (showreel title move). */
  const rise = (
    s: string,
    x: number,
    y: number,
    o: TextOpts & { t: number; t0: number; stagger?: number; dur?: number; tout?: number },
  ) => {
    const { size = 120, weight = 800, fam = 'display', color = C.paper, align = 'left', stagger = 0.028, dur = 0.5, ls = -0.02 } = o
    setFont(size, weight, fam, ls)
    const full = ctx.measureText(s).width
    const sx = align === 'center' ? x - full / 2 : align === 'right' ? x - full : x
    ctx.save()
    ctx.beginPath()
    ctx.rect(sx - 40, y - size * 1.1, full + 80, size * 1.45)
    ctx.clip()
    ctx.fillStyle = color
    ctx.textAlign = 'left'
    ctx.textBaseline = 'alphabetic'
    for (let i = 0; i < s.length; i++) {
      const px = sx + ctx.measureText(s.slice(0, i)).width
      const k = outExpo(seg(o.t, o.t0 + i * stagger, o.t0 + i * stagger + dur))
      let dy = (1 - k) * size * 1.2
      if (o.tout !== undefined) dy -= outCubic(seg(o.t, o.tout + i * 0.012, o.tout + i * 0.012 + 0.3)) * size * 1.3
      ctx.fillText(s[i], px, y + dy)
    }
    ctx.restore()
    return full
  }

  /** Substring typed so far, for a typing effect over progress k. */
  const typed = (s: string, k: number) => s.slice(0, Math.round(clamp(k) * s.length))

  const rr = (x: number, y: number, w: number, h: number, r: number) => {
    ctx.beginPath()
    ctx.roundRect(x, y, w, h, Math.min(r, Math.abs(w) / 2, Math.abs(h) / 2))
  }
  const fillRR = (x: number, y: number, w: number, h: number, r: number, color: string) => {
    rr(x, y, w, h, r)
    ctx.fillStyle = color
    ctx.fill()
  }
  const strokeRR = (x: number, y: number, w: number, h: number, r: number, color: string, lw = 2) => {
    rr(x, y, w, h, r)
    ctx.strokeStyle = color
    ctx.lineWidth = lw
    ctx.stroke()
  }

  const line = (x1: number, y1: number, x2: number, y2: number, color: string, lw = 2, dash?: number[]) => {
    ctx.save()
    ctx.strokeStyle = color
    ctx.lineWidth = lw
    ctx.lineCap = 'round'
    if (dash) ctx.setLineDash(dash)
    ctx.beginPath()
    ctx.moveTo(x1, y1)
    ctx.lineTo(x2, y2)
    ctx.stroke()
    ctx.restore()
  }

  /** Draw a polyline through `pts` up to progress k (0..1 of its length). */
  const trace = (
    pts: readonly { x: number; y: number }[],
    k: number,
    o: { color: string; lw?: number; dash?: number[]; cap?: CanvasLineCap } = { color: C.paper },
  ) => {
    if (pts.length < 2 || k <= 0) return pts[0]
    const lens = [0]
    for (let i = 1; i < pts.length; i++) lens.push(lens[i - 1] + Math.hypot(pts[i].x - pts[i - 1].x, pts[i].y - pts[i - 1].y))
    const L = lens[lens.length - 1] * clamp(k)
    ctx.save()
    ctx.strokeStyle = o.color
    ctx.lineWidth = o.lw ?? 3
    ctx.lineCap = o.cap ?? 'round'
    ctx.lineJoin = 'round'
    if (o.dash) ctx.setLineDash(o.dash)
    ctx.beginPath()
    ctx.moveTo(pts[0].x, pts[0].y)
    let end = pts[0]
    for (let i = 1; i < pts.length; i++) {
      if (lens[i] <= L) {
        ctx.lineTo(pts[i].x, pts[i].y)
        end = pts[i]
      }
      else {
        const f = (L - lens[i - 1]) / (lens[i] - lens[i - 1] || 1)
        end = { x: pts[i - 1].x + (pts[i].x - pts[i - 1].x) * f, y: pts[i - 1].y + (pts[i].y - pts[i - 1].y) * f }
        ctx.lineTo(end.x, end.y)
        break
      }
    }
    ctx.stroke()
    ctx.restore()
    return end
  }

  /** Sample a function into points, for trace(). */
  const sample = (f: (u: number) => { x: number; y: number }, n = 60) =>
    Array.from({ length: n + 1 }, (_, i) => f(i / n))

  const arrow = (
    x1: number, y1: number, x2: number, y2: number,
    o: { color?: string; lw?: number; k?: number; head?: number; dash?: number[] } = {},
  ) => {
    const { color = C.dim, lw = 3, k = 1, head = 14 } = o
    if (k <= 0) return
    const ex = x1 + (x2 - x1) * clamp(k)
    const ey = y1 + (y2 - y1) * clamp(k)
    line(x1, y1, ex, ey, color, lw, o.dash)
    const a = Math.atan2(y2 - y1, x2 - x1)
    ctx.save()
    ctx.fillStyle = color
    ctx.beginPath()
    ctx.moveTo(ex, ey)
    ctx.lineTo(ex - head * Math.cos(a - 0.45), ey - head * Math.sin(a - 0.45))
    ctx.lineTo(ex - head * Math.cos(a + 0.45), ey - head * Math.sin(a + 0.45))
    ctx.closePath()
    ctx.fill()
    ctx.restore()
  }

  const dot = (x: number, y: number, r: number, color: string) => {
    ctx.fillStyle = color
    ctx.beginPath()
    ctx.arc(x, y, Math.max(0, r), 0, Math.PI * 2)
    ctx.fill()
  }

  /**
   * A token chip. k is its entry progress (scale-pop with a tiny overshoot).
   * Returns the chip width so rows can be laid out.
   */
  const chip = (
    label: string,
    x: number,
    y: number,
    o: { bg?: string; fg?: string; size?: number; k?: number; fam?: Fam; weight?: number; h?: number; pad?: number; align?: 'left' | 'center'; stroke?: string } = {},
  ) => {
    const { bg = C.blueDeep, fg = C.blueText, size = 30, k = 1, fam = 'mono', weight = 500, pad = 16, align = 'left' } = o
    const h = o.h ?? size * 1.7
    const w = measure(label, size, weight, fam) + pad * 2
    if (k <= 0) return w
    const s = 0.6 + 0.4 * outBack(k)
    const x0 = align === 'center' ? x - w / 2 : x
    ctx.save()
    ctx.globalAlpha *= clamp(k * 3)
    ctx.translate(x0 + w / 2, y + h / 2)
    ctx.scale(s, s)
    fillRR(-w / 2, -h / 2, w, h, 10, bg)
    if (o.stroke) strokeRR(-w / 2, -h / 2, w, h, 10, o.stroke, 2)
    text(label, 0, 1, { size, weight, fam, color: fg, align: 'center', base: 'middle' })
    ctx.restore()
    return w
  }


  /** A small mono label, the deck's axis/caption voice. */
  const label = (s: string, x: number, y: number, o: TextOpts = {}) =>
    text(s, x, y, { size: 24, weight: 500, fam: 'mono', color: C.mute, ...o })

  /**
   * Phase stepper, bottom-right: "1 see · 2 understand · 3 act". A real
   * sequence, so the room always knows which part of the loop it is watching.
   */
  const stepper = (items: readonly string[], active: number, a = 1, y = H - 52) => {
    if (a <= 0) return
    let x = W - MX
    for (let i = items.length - 1; i >= 0; i--) {
      const s = `${i + 1} ${items[i]}`
      const w = measure(s, 24, 500, 'mono')
      const on = i === active
      text(s, x, y, { size: 24, weight: 500, fam: 'mono', color: on ? C.paper : C.mute, align: 'right', alpha: a * (on ? 1 : 0.7) })
      if (on) {
        ctx.save()
        ctx.globalAlpha *= a
        ctx.fillStyle = C.yellow
        ctx.fillRect(x - w, y + 8, w, 3)
        ctx.restore()
      }
      x -= w + 40
    }
  }

  /** Source line, bottom-left: every number on screen names where it came from. */
  const cite = (s: string, a = 1) => text(s, MX, H - 48, { size: 22, weight: 400, fam: 'mono', color: C.mute, alpha: a * 0.9 })

  /** A number that counts from a to b over progress k, with thousands separators. */
  const count = (a: number, b: number, k: number, sep = ' ') =>
    Math.round(a + (b - a) * outExpo(k)).toString().replace(/\B(?=(\d{3})+(?!\d))/g, sep)

  /** Run fn with extra alpha; skip entirely at zero. */
  const fade = (a: number, fn: () => void) => {
    if (a <= 0.001) return
    ctx.save()
    ctx.globalAlpha *= clamp(a)
    fn()
    ctx.restore()
  }

  /** Run fn inside a camera: zoom z about (cx, cy), then pan so (cx, cy) lands at (tx, ty). */
  const camera = (z: number, cx: number, cy: number, fn: () => void, tx = W / 2, ty = H / 2) => {
    ctx.save()
    ctx.translate(tx, ty)
    ctx.scale(z, z)
    ctx.translate(-cx, -cy)
    fn()
    ctx.restore()
  }

  const clear = (color: string = C.bg) => {
    ctx.fillStyle = color
    ctx.fillRect(-10, -10, W + 20, H + 20)
  }

  /** Faint engineering grid: gives the stage depth without a surface colour. */
  const grid = (a = 0.05, step = 120) => {
    ctx.save()
    ctx.strokeStyle = alpha(C.paper, a)
    ctx.lineWidth = 1
    ctx.beginPath()
    for (let x = step; x < W; x += step) {
      ctx.moveTo(x, 0)
      ctx.lineTo(x, H)
    }
    for (let y = step; y < H; y += step) {
      ctx.moveTo(0, y)
      ctx.lineTo(W, y)
    }
    ctx.stroke()
    ctx.restore()
  }

  /** Slide title, top-left, kinetic. One per scene; `*accent*` words allowed. */
  const title = (s: string, t: number, t0 = 0.1, o: { tout?: number; size?: number; maxW?: number } = {}) =>
    words(s, MX, 150, { t, t0, size: o.size ?? 56, weight: 700, fam: 'display', maxW: o.maxW ?? 1500, lh: 1.1, tout: o.tout })

  /**
   * The punchline: a kinetic sentence in Instrument Sans, usually near the
   * bottom. `*accent*` words take the action amber.
   */
  const punch = (s: string, t: number, t0: number, o: { x?: number; y?: number; size?: number; maxW?: number; align?: CanvasTextAlign; tout?: number; accent?: string } = {}) =>
    words(s, o.x ?? MX, o.y ?? H - 140, { t, t0, size: o.size ?? 44, weight: 600, fam: 'sans', ls: -0.01, maxW: o.maxW ?? 1700, align: o.align ?? 'left', tout: o.tout, accent: o.accent, stagger: 0.03 })

  return {
    title, punch,
    ctx, setFont, measure, text, wrap, words, rise, typed,
    rr, fillRR, strokeRR, line, trace, sample, arrow, dot, chip,
    label, stepper, cite, count, fade, camera, clear, grid,
  }
}

export type Kit = ReturnType<typeof makeKit>
