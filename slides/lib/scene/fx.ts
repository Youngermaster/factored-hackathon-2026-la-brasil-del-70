/**
 * Colour fields and mechanism effects: the accents as confident fills, and the
 * small motions that show a mechanism (a packet flowing, a ring where
 * something is blocked). Stateless like the rest of the kit: pass progress k.
 */
import { C, H, W, type Kit } from './kit'
import { clamp, inOutCubic, outCubic } from './math'
import { along } from './bank'

type Pt = { x: number; y: number }
export type From = 'left' | 'right' | 'top' | 'bottom'

/** A rectangle revealed by a wipe from one edge over k (0..1, already eased or not). */
export function field(K: Kit, x: number, y: number, w: number, h: number, color: string, k: number, from: From = 'left', r = 0) {
  if (k <= 0) return
  const e = inOutCubic(clamp(k))
  const [rx, ry, rw, rh] =
    from === 'left' ? [x, y, w * e, h]
      : from === 'right' ? [x + w * (1 - e), y, w * e, h]
        : from === 'top' ? [x, y, w, h * e]
          : [x, y + h * (1 - e), w, h * e]
  if (r > 0) K.fillRR(rx, ry, rw, rh, r, color)
  else {
    K.ctx.fillStyle = color
    K.ctx.fillRect(rx, ry, rw, rh)
  }
}

/** Run fn clipped to a rectangle revealed by a wipe, so content can change colour as a field floods in. */
export function clipWipe(K: Kit, x: number, y: number, w: number, h: number, k: number, from: From, fn: () => void) {
  if (k <= 0) return
  const e = inOutCubic(clamp(k))
  const ctx = K.ctx
  ctx.save()
  ctx.beginPath()
  if (from === 'left') ctx.rect(x, y, w * e, h)
  else if (from === 'right') ctx.rect(x + w * (1 - e), y, w * e, h)
  else if (from === 'top') ctx.rect(x, y, w, h * e)
  else ctx.rect(x, y + h * (1 - e), w, h * e)
  ctx.clip()
  fn()
  ctx.restore()
}

/** The full-bleed ground, for a slide or a moment that owns a colour. */
export const ground = (K: Kit, color: string, k = 1, from: From = 'bottom') => field(K, -4, -4, W + 8, H + 8, color, k, from)

/** A packet travelling a path: u is its position (0..1); it trails a short tail. */
export function packet(K: Kit, pts: readonly Pt[], u: number, color: string, r = 10) {
  if (u <= 0 || u >= 1) return
  for (let i = 3; i >= 1; i--) {
    const p = along(pts, clamp(u - i * 0.025))
    K.fade(0.18 * (4 - i), () => K.dot(p.x, p.y, r * (1 - i * 0.18), color))
  }
  const p = along(pts, u)
  K.dot(p.x, p.y, r, color)
}

/** One ring that expands and fades where something is blocked or lands. */
export function ring(K: Kit, x: number, y: number, k: number, color: string, r0 = 8, r1 = 70) {
  if (k <= 0 || k >= 1) return
  const e = outCubic(k)
  K.ctx.save()
  K.ctx.globalAlpha *= 1 - e
  K.ctx.strokeStyle = color
  K.ctx.lineWidth = 5
  K.ctx.beginPath()
  K.ctx.arc(x, y, r0 + (r1 - r0) * e, 0, Math.PI * 2)
  K.ctx.stroke()
  K.ctx.restore()
}

export type GlyphKind = 'clause' | 'states' | 'verified' | 'handoff' | 'lang' | 'eval'

/**
 * Small drawn glyphs for the depth checkpoints (no icon font, so they stay
 * crisp in the PDF). s is the glyph size; k draws it on.
 */
export function glyph(K: Kit, kind: GlyphKind, cx: number, cy: number, s: number, color: string, k = 1) {
  if (k <= 0) return
  const h = s / 2
  const lw = Math.max(3, s * 0.09)
  K.fade(clamp(k * 2), () => {
    const ctx = K.ctx
    ctx.save()
    ctx.translate(cx, cy)
    const sc = 0.7 + 0.3 * outCubic(k)
    ctx.scale(sc, sc)
    ctx.strokeStyle = color
    ctx.fillStyle = color
    ctx.lineWidth = lw
    ctx.lineCap = 'round'
    ctx.lineJoin = 'round'
    if (kind === 'clause') {
      ctx.strokeRect(-h * 0.7, -h, h * 1.4, s)
      for (let i = 0; i < 3; i++) K.line(-h * 0.4, -h * 0.5 + i * h * 0.45, h * 0.4, -h * 0.5 + i * h * 0.45, color, lw * 0.8)
    }
    else if (kind === 'states') {
      const pts = [[-h, h * 0.5], [0, -h * 0.6], [h, h * 0.5]]
      K.line(pts[0][0], pts[0][1], pts[1][0], pts[1][1], color, lw)
      K.line(pts[1][0], pts[1][1], pts[2][0], pts[2][1], color, lw)
      for (const [x, y] of pts) K.dot(x, y, s * 0.15, color)
    }
    else if (kind === 'verified') {
      ctx.beginPath()
      ctx.arc(0, 0, h, 0, Math.PI * 2)
      ctx.stroke()
      K.trace([{ x: -h * 0.45, y: 0 }, { x: -h * 0.1, y: h * 0.35 }, { x: h * 0.5, y: -h * 0.35 }], 1, { color, lw })
    }
    else if (kind === 'handoff') {
      ctx.beginPath()
      ctx.arc(h * 0.35, -h * 0.35, h * 0.3, 0, Math.PI * 2)
      ctx.fill()
      ctx.beginPath()
      ctx.arc(h * 0.35, h * 0.75, h * 0.6, Math.PI, 0)
      ctx.fill()
      K.arrow(-h, 0, -h * 0.1, 0, { color, lw, head: s * 0.22 })
    }
    else if (kind === 'lang') {
      // text, not a pictogram: kept at the deck's 22 px minimum whatever the glyph size
      K.text('es pt', 0, 0, { size: Math.max(22, s * 0.62), weight: 700, fam: 'mono', color, align: 'center', base: 'middle' })
    }
    else {
      for (let i = 0; i < 3; i++) {
        const bh = s * (0.35 + i * 0.3)
        ctx.fillRect(-h + i * h * 0.75, h - bh, h * 0.5, bh)
      }
    }
    ctx.restore()
  })
}

/** The ink colour to write on a given fill (AA-checked pairs in contrast.ts). */
export const inkOn = (fill: string) => (fill === C.blue || fill === C.yellow || fill === C.paper || fill === C.red ? C.bg : C.paper)
