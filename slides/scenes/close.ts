/**
 * Slide 6, honest limits, the route to operation, the team, the close.
 *
 *   arrive  four limit tiles drop in, each with a red band (risk)
 *   1       the route to operation: in place (yellow chips) and next
 *   2       the team on a full-bleed yellow field
 *   3       the yellow field folds into the middle band of the thesis; the
 *           other two bands wipe in; repository and deployment link below
 */
import { defineScene } from '../lib/scene/types'
import { C, H, MX, W } from '../lib/scene/kit'
import { clamp, inOutCubic, lerp, outCubic, outExpo, presence, seg } from '../lib/scene/math'
import { metricValue, tab } from '../lib/scene/bank'
import { field } from '../lib/scene/fx'

const BAND_Y = [180, 350, 520] as const
const BAND_H = 170

export default defineScene({
  cues: [2.8, 5.8, 8.4, 10.8],
  draw({ t, L, M, K }) {
    const heading = (key: string, t0: number, tout?: number) =>
      K.words(L(key), MX, 150, { t, t0, tout, size: 56, weight: 700, fam: 'display' })

    // ── arrive: four limit tiles ───────────────────────────────────────────
    heading('limitsTitle', 0.1, 2.85)
    K.fade(presence(t, 0.2, 2.85, 0.3, 0.25), () => {
      for (let i = 0; i < 4; i++) {
        const x = MX + i * 430
        field(K, x, 300, 390, 330, C.bg2, seg(t, 0.4 + i * 0.15, 0.9 + i * 0.15), 'top', 12)
        field(K, x, 300, 390, 12, C.red, seg(t, 0.8 + i * 0.15, 1.2 + i * 0.15), 'left', 6)
        const k = outExpo(seg(t, 0.9 + i * 0.15, 1.5 + i * 0.15))
        K.fade(clamp(k * 2), () => {
          K.wrap(L(`l${i + 1}`), 330, 40, 700, 'display').forEach((ln, j) =>
            K.text(ln, x + 32, 400 + j * 48 + (1 - k) * 20, { size: 40, weight: 700, fam: 'display' }))
          K.wrap(L(`l${i + 1}s`), 330, 28, 500).forEach((ln, j) =>
            K.text(ln, x + 32, 560 + j * 36, { size: 28, weight: 500, color: C.dim }))
        })
      }
    })

    // ── 1 route to operation: in place, next ───────────────────────────────
    heading('routeTitle', 3.0, 5.85)
    K.fade(presence(t, 2.9, 5.85, 0.3, 0.25), () => {
      K.label(L('inPlace'), MX, 320, { size: 24, color: C.yellow, alpha: outCubic(seg(t, 3.1, 3.4)) })
      let x = MX
      for (let i = 1; i <= 5; i++) x += tab(K, L(`i${i}`), x, 350, { tone: 'yellow', k: seg(t, 3.2 + i * 0.1, 3.6 + i * 0.1), size: 30 }) + 18
      K.label(L('remaining'), MX, 540, { size: 24, color: C.dim, alpha: outCubic(seg(t, 3.9, 4.2)) })
      x = MX
      for (let i = 1; i <= 5; i++) {
        const w = K.chip(L(`r${i}`), x, 570, { bg: C.bg2, fg: C.paper, k: seg(t, 4.0 + i * 0.1, 4.4 + i * 0.1), size: 30, weight: 500 })
        K.fade(outCubic(seg(t, 4.2 + i * 0.1, 4.5 + i * 0.1)), () => K.strokeRR(x, 570, w, 51, 10, C.dim, 2))
        x += w + 18
      }
      K.fade(outCubic(seg(t, 4.8, 5.2)), () => {
        K.label(L('deployed'), MX, 790, { size: 24 })
        metricValue(K, M('deploy.url'), MX + 200, 800, { size: 40, fam: 'mono' })
      })
    })

    // ── 2 team on yellow, 3 the field folds into the middle band ──────────
    const fold = inOutCubic(seg(t, 8.5, 9.2))
    const gk = seg(t, 5.9, 6.4)
    if (gk > 0) {
      if (fold <= 0) field(K, -4, -4, W + 8, H + 8, C.yellow, gk, 'bottom')
      else K.fillRR(-4, lerp(-4, BAND_Y[1], fold), W + 8, lerp(H + 8, BAND_H, fold), 0, C.yellow)
    }
    K.fade(presence(t, 6.0, 8.45, 0.3, 0.2), () => {
      K.words(L('teamTitle'), MX, 380, { t, t0: 6.2, size: 96, weight: 800, fam: 'display', color: C.bg, stagger: 0.05 })
      for (let i = 0; i < 4; i++) {
        const x = i % 2 ? 1000 : MX
        const y = 590 + Math.floor(i / 2) * 190
        const k = outExpo(seg(t, 6.6 + i * 0.15, 7.3 + i * 0.15))
        K.fade(clamp(k * 2), () => {
          K.text(L(`m${i + 1}`), x, y + (1 - k) * 24, { size: 52, weight: 700, fam: 'display', color: C.bg })
          K.text(L(`m${i + 1}r`), x, y + 52 + (1 - k) * 24, { size: 28, weight: 500, fam: 'mono', color: C.inkDim })
        })
      }
    })

    // the thesis bands: blue and paper wipe in around the yellow one
    field(K, -4, BAND_Y[0], W + 8, BAND_H, C.blue, seg(t, 9.0, 9.6), 'left')
    field(K, -4, BAND_Y[2], W + 8, BAND_H, C.paper, seg(t, 9.2, 9.8), 'right')
    ;(['c1', 'c2', 'c3'] as const).forEach((key, i) =>
      K.words(L(key), MX, BAND_Y[i] + 110, { t, t0: 9.3 + i * 0.2, size: 72, weight: 800, fam: 'display', color: C.bg, accent: C.bg, stagger: 0.04 }))
    K.fade(outCubic(seg(t, 9.9, 10.3)), () => {
      K.text(L('repo'), MX, 800, { size: 30, weight: 500, fam: 'mono', color: C.dim })
      K.label(L('deployed'), MX, 880, { size: 24 })
      metricValue(K, M('deploy.url'), MX + 200, 890, { size: 40, fam: 'mono' })
    })
  },
})
