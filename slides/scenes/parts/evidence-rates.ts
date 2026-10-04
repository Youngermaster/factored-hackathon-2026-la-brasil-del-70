/**
 * The rate charts of the evidence scene (scenes/evidence.ts): safe automated
 * resolution per workflow with its intervals, then the aggregate and the
 * trade-offs (missed and unnecessary transfers, latency). The three systems
 * keep one colour each across the slide: P yellow (deterministic code
 * decides), B0 light gray (the menu and rules bot), B1 blue (the model alone).
 */
import type { SceneEnv } from '../../lib/scene/types'
import { C, MX, type Kit } from '../../lib/scene/kit'
import { clamp, outCubic, outExpo, presence, seg } from '../../lib/scene/math'
import type { Metric } from '../../lib/metrics'

export const SYS = ['p', 'b0', 'b1'] as const
export const SYS_MAIN = [C.yellow, C.dim, C.blue] as const
export const SYS_TEXT = [C.yellow, C.dim, C.blueText] as const
export const WF = ['account_inquiry', 'card_support', 'dispute', 'credit'] as const
/** fraction columns, centred; the system tabs sit above them in clicks 1 and 2 */
export const COLX = [1480, 1620, 1760] as const
const X0 = 520
const X1 = 1380
export const sx = (v: number) => X0 + ((X1 - X0) * v) / 100

/** A system tab: ink on the system's fill. Returns its width. */
export function sysTab(K: Kit, L: (k: string) => string, i: number, x: number, y: number, k = 1, size = 24) {
  return K.chip(L(`sys${i}`), x, y, { bg: SYS_MAIN[i], fg: C.bg, k, size, weight: 700, align: 'center' })
}

/** An interval bar with its point estimate, drawn outward from the point over k. */
function interval(K: Kit, m: Metric, y: number, i: number, k: number, h = 10) {
  if (k <= 0 || m.pending) return
  const e = outExpo(k)
  const c = sx(m.num)
  const a = c - (c - sx(m.lo)) * e
  const b = c + (sx(m.hi) - c) * e
  K.fade(clamp(k * 3), () => {
    K.fillRR(a, y - h / 2, Math.max(h, b - a), h, h / 2, SYS_MAIN[i])
    K.dot(c, y, h * 1.15, SYS_MAIN[i])
    K.dot(c, y, h * 0.55, C.bg)
  })
}

/** Click 1: per workflow first. Click 2: the rows fold into the aggregate. */
export function rates({ t, L, M, K }: SceneEnv, c1: number, c2: number, c3: number) {
  // ── 1 per workflow ────────────────────────────────────────────────────
  K.fade(presence(t, c1, c2, 0.3, 0.25), () => {
    K.label(L('sarLbl'), MX, 228, { size: 24, color: C.dim, alpha: outCubic(seg(t, c1 + 0.2, c1 + 0.5)) })
    WF.forEach((w, r) => {
      const y = 380 + r * 150
      const t0 = c1 + 0.3 + r * 0.25
      K.fade(outCubic(seg(t, t0, t0 + 0.3)), () => K.text(L(w), MX, y + 10, { size: 30, weight: 600 }))
      K.fade(outCubic(seg(t, t0, t0 + 0.3)) * 0.5, () => K.line(X0, y + 64, X1, y + 64, C.faint, 2))
      SYS.forEach((s, i) => {
        const m = M(`eval.sar.${w}.${s}`)
        interval(K, m, y - 34 + i * 34, i, seg(t, t0 + 0.15 + i * 0.1, t0 + 0.75 + i * 0.1))
        K.fade(outCubic(seg(t, t0 + 0.4 + i * 0.1, t0 + 0.7 + i * 0.1)), () =>
          K.text(m.text, COLX[i], y + 10, { size: 26, weight: 500, fam: 'mono', color: SYS_TEXT[i], align: 'center' }))
      })
      // the honest weak spot: card support is not ahead of B0
      if (w === 'card_support') {
        const k = seg(t, c1 + 2.0, c1 + 2.5)
        if (k > 0) K.fillRR(MX - 34, y - 52, 8, 104 * outExpo(k), 4, C.red)
        K.fade(outCubic(k), () => K.label(L('notAhead'), MX, y + 48, { size: 22, color: C.redText }))
      }
    })
    K.fade(outCubic(seg(t, c1 + 1.6, c1 + 2.0)), () => K.label(L('intervalNote'), X0, 990 - 30, { size: 22 }))
  })

  // ── 2 the aggregate and the trade-offs ────────────────────────────────
  K.fade(presence(t, c2 + 0.1, c3, 0.3, 0.25), () => {
    K.label(L('aggLbl'), MX, 228, { size: 24, color: C.dim, alpha: outCubic(seg(t, c2 + 0.2, c2 + 0.5)) })
    SYS.forEach((s, i) => {
      const m = M(`eval.sar.all.${s}`)
      const y = 330 + i * 78
      const k = seg(t, c2 + 0.3 + i * 0.15, c2 + 1.1 + i * 0.15)
      interval(K, m, y, i, k, 20)
      K.fade(outCubic(seg(t, c2 + 0.8 + i * 0.15, c2 + 1.2 + i * 0.15)), () => {
        K.text(`${Math.round(m.num)}%`, sx(m.hi) + 28, y + 18, { size: 48, weight: 800, fam: 'display', color: SYS_TEXT[i] })
        K.text(m.text, COLX[i], y + 10, { size: 26, weight: 500, fam: 'mono', color: SYS_TEXT[i], align: 'center' })
      })
    })
    K.fade(outCubic(seg(t, c2 + 0.5, c2 + 0.9)), () => K.text(L('sarShort'), MX, 418, { size: 30, weight: 600 }))
    // the trade-offs: thin bars on the same scale, one per system
    // metric families eval.missed.*, eval.unnecessary.*, eval.latency_p50.*
    const rows = [['missed', true], ['unnecessary', true], ['latency_p50', false]] as const
    rows.forEach(([fam, bar], r) => {
      const y = 640 + r * 112
      const t0 = c2 + 1.4 + r * 0.3
      K.fade(outCubic(seg(t, t0, t0 + 0.3)), () => K.text(L(fam), MX, y + 10, { size: 28, weight: 500 }))
      SYS.forEach((s, i) => {
        const m = M(`eval.${fam}.${s}`)
        if (bar) {
          const w = (X1 - X0) * (m.num / m.of) * outExpo(seg(t, t0 + 0.1 + i * 0.08, t0 + 0.8 + i * 0.08))
          if (w > 0) K.fillRR(X0, y - 18 + i * 14, Math.max(6, w), 8, 4, SYS_MAIN[i])
        }
        K.fade(outCubic(seg(t, t0 + 0.3 + i * 0.08, t0 + 0.6 + i * 0.08)), () =>
          K.text(m.text, COLX[i], y + 10, { size: 26, weight: 500, fam: 'mono', color: SYS_TEXT[i], align: 'center' }))
      })
    })
  })
}
