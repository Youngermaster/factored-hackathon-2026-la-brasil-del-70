/**
 * Boxes and connectors for the architecture scene (scenes/arch.ts), drawn on
 * the light-gray ground. The colour keeps its meaning: blue is a model
 * (understanding), yellow is deterministic code deciding or acting, ink is a
 * store, a server, or plumbing, dashed is optional or "by setting".
 *
 *   ink     ink fill, paper label, dim sub-label
 *   blue    blue fill, ink label and sub-label (4.8:1)
 *   yellow  yellow fill, ink label, inkDim sub-label
 *   dashed  ink dashed outline, ink label, inkDim sub-label
 */
import type { Kit } from '../../lib/scene/kit'
import { C } from '../../lib/scene/kit'
import { clamp, outCubic, outExpo } from '../../lib/scene/math'

export type BoxKind = 'ink' | 'blue' | 'yellow' | 'dashed'

const COLORS: Record<BoxKind, { fill?: string; fg: string; sub: string }> = {
  ink: { fill: C.bg, fg: C.paper, sub: C.dim },
  blue: { fill: C.blue, fg: C.bg, sub: C.bg },
  yellow: { fill: C.yellow, fg: C.bg, sub: C.inkDim },
  dashed: { fg: C.bg, sub: C.inkDim },
}

/** A labelled box that rises in over k. Returns its centre and edges for connectors. */
export function box(K: Kit, kind: BoxKind, x: number, y: number, w: number, h: number, label: string, sub: string, k: number, size = 28) {
  const c = COLORS[kind]
  const geo = { x, y, w, h, cx: x + w / 2, cy: y + h / 2, r: x + w, b: y + h }
  if (k <= 0) return geo
  K.fade(clamp(k * 2), () => {
    const dy = (1 - outExpo(k)) * 20
    if (c.fill) K.fillRR(x, y + dy, w, h, 10, c.fill)
    else {
      K.ctx.save()
      K.ctx.setLineDash([9, 7])
      K.strokeRR(x, y + dy, w, h, 10, C.bg, 2)
      K.ctx.restore()
    }
    const cy = y + dy + h / 2
    K.text(label, x + 24, sub ? cy - 4 : cy + 10, { size, weight: 700, color: c.fg })
    if (sub) K.text(sub, x + 24, cy + 30, { size: 22, weight: 500, fam: 'mono', color: c.sub })
  })
  return geo
}

/** A connector drawn on over k: a polyline with an arrowhead at its end. */
export function wire(K: Kit, pts: readonly { x: number; y: number }[], k: number, color: string = C.bg, lw = 3) {
  if (k <= 0) return
  const end = K.trace(pts, outCubic(k), { color, lw })
  if (k < 0.98 || !end) return
  const a = pts[pts.length - 2]
  const b = pts[pts.length - 1]
  K.arrow(a.x + (b.x - a.x) * 0.9, a.y + (b.y - a.y) * 0.9, b.x, b.y, { color, lw, head: 14 })
}

/** A dashed outline region (a host, a profile) drawn on over k, with its label inside the top-left corner. */
export function region(K: Kit, x: number, y: number, w: number, h: number, label: string, k: number, dashed = true, bottom = false) {
  if (k <= 0) return
  K.fade(clamp(k * 2), () => {
    K.ctx.save()
    if (dashed) K.ctx.setLineDash([12, 9])
    K.strokeRR(x, y, w, h, 16, C.bg, dashed ? 2 : 3)
    K.ctx.restore()
    K.text(label, x + 24, bottom ? y + h - 20 : y + 40, { size: 24, weight: 600, fam: 'mono', color: C.inkDim })
  })
}
