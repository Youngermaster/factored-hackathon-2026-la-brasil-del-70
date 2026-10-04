/**
 * Slide 6: reliability, security, honest limits, the team, the close.
 *
 *   arrive  the degradation ladder: failures push the service down L0 to L4;
 *           writes are verified at every level and L4 writes nothing
 *   1       defense in depth: one request lane, every attack stops at its layer
 *   2       what we cannot claim yet (red), and the real next steps as a route
 *   3       the team on a full-bleed yellow field
 *   4       the yellow field folds into the middle band of the thesis; the
 *           product name, the repository and the deployed URL
 */
import { defineScene } from '../lib/scene/types'
import { C, H, MX, W } from '../lib/scene/kit'
import { clamp, inOutCubic, lerp, outCubic, outExpo, presence, seg } from '../lib/scene/math'
import { dims, metricValue } from '../lib/scene/bank'
import { field, packet } from '../lib/scene/fx'
import { ladder } from './parts/close-ladder'
import { defense } from './parts/close-defense'

const CUES = [3.6, 7.4, 10.8, 13.4, 15.8] as const
const BAND_Y = [200, 370, 540] as const
const BAND_H = 170
const MEMBERS = 4

export default defineScene({
  cues: CUES,
  draw(env) {
    const { t, L, M, K } = env
    const c = [0, CUES[0] + 0.05, CUES[1] + 0.05, CUES[2] + 0.05, CUES[3] + 0.05]
    K.title(L('ladderTitle'), t, 0.1, { tout: c[1] })
    K.title(L('defenseTitle'), t, c[1] + 0.1, { tout: c[2] })
    K.title(L('limitsTitle'), t, c[2] + 0.1, { tout: c[3] })
    K.fade(presence(t, 1.4, c[3], 0.3, 0.2), () => K.cite(L(t < c[1] ? 'citeLadder' : t < c[2] ? 'citeDefense' : 'citeLimits')))

    ladder(env, c[1])
    defense(env, c[1], c[2])

    // ── 2 limits on the left, next steps as a route on the right ──────────
    K.fade(presence(t, c[2], c[3], 0.3, 0.25), () => {
      for (let i = 0; i < 4; i++) {
        const y = 330 + i * 130
        const k = seg(t, c[2] + 0.2 + i * 0.12, c[2] + 0.6 + i * 0.12)
        if (k > 0) K.fillRR(MX, y - 34, 10, 76 * outExpo(k), 5, C.red)
        K.fade(outCubic(k), () => {
          K.text(L(`l${i}`), MX + 36, y + 2, { size: 36, weight: 700, fam: 'display' })
          K.text(L(`l${i}s`), MX + 36, y + 40, { size: 24, weight: 500, color: C.dim })
        })
      }
      const RX = 1060
      K.fade(outCubic(seg(t, c[2] + 0.6, c[2] + 0.9)), () => K.label(L('nextLbl'), RX, 266, { size: 24 }))
      const route = [{ x: RX + 14, y: 316 }, { x: RX + 14, y: 316 + 3 * 130 }]
      K.trace(route, outCubic(seg(t, c[2] + 0.8, c[2] + 2.0)), { color: C.faint, lw: 4 })
      packet(K, route, seg(t, c[2] + 0.8, c[2] + 2.0), C.paper, 9)
      for (let i = 0; i < 4; i++) {
        const y = 316 + i * 130
        const k = seg(t, c[2] + 0.9 + i * 0.3, c[2] + 1.3 + i * 0.3)
        K.fade(outCubic(k), () => {
          K.dot(RX + 14, y, 14, C.paper)
          K.dot(RX + 14, y, 7, C.bg)
          K.text(L(`n${i}`), RX + 52, y + 11, { size: 32, weight: 600 })
        })
      }
    })

    // ── 3 team on yellow, 4 the field folds into the middle band ──────────
    const fold = inOutCubic(seg(t, c[4], c[4] + 0.7))
    const gk = seg(t, c[3], c[3] + 0.5)
    if (gk > 0) {
      if (fold <= 0) field(K, -4, -4, W + 8, H + 8, C.yellow, gk, 'bottom')
      else K.fillRR(-4, lerp(-4, BAND_Y[1], fold), W + 8, lerp(H + 8, BAND_H, fold), 0, C.yellow)
    }
    K.fade(presence(t, c[3] + 0.1, c[4], 0.3, 0.2), () => {
      K.label(L('product'), MX, 250, { size: 26, color: C.inkDim, alpha: outCubic(seg(t, c[3] + 0.3, c[3] + 0.6)) })
      K.words(L('teamTitle'), MX, 380, { t, t0: c[3] + 0.3, size: 96, weight: 800, fam: 'display', color: C.bg, stagger: 0.05 })
      for (let i = 0; i < MEMBERS; i++) {
        const x = i % 2 ? 1000 : MX
        const y = 590 + Math.floor(i / 2) * 190
        const k = outExpo(seg(t, c[3] + 0.6 + i * 0.15, c[3] + 1.3 + i * 0.15))
        K.fade(clamp(k * 2), () => {
          K.text(L(`m${i + 1}`), x, y + (1 - k) * 24, { size: 52, weight: 700, fam: 'display', color: C.bg })
          K.text(L(`m${i + 1}r`), x, y + 52 + (1 - k) * 24, { size: 28, weight: 500, fam: 'mono', color: C.inkDim })
        })
      }
    })

    // the thesis bands: blue and paper wipe in around the yellow one
    field(K, -4, BAND_Y[0], W + 8, BAND_H, C.blue, seg(t, c[4] + 0.5, c[4] + 1.1), 'left')
    field(K, -4, BAND_Y[2], W + 8, BAND_H, C.paper, seg(t, c[4] + 0.7, c[4] + 1.3), 'right')
    ;(['c1', 'c2', 'c3'] as const).forEach((key, i) =>
      K.words(L(key), MX, BAND_Y[i] + 110, { t, t0: c[4] + 0.8 + i * 0.2, size: 72, weight: 800, fam: 'display', color: C.bg, accent: C.bg, stagger: 0.04 }))
    K.fade(outCubic(seg(t, c[4] + 1.3, c[4] + 1.7)), () => {
      K.text(L('product'), MX, 140, { size: 40, weight: 700, fam: 'display' })
      K.label(L('teamTitle'), MX + K.measure(L('product'), 40, 700, 'display') + 32, 138, { size: 26, color: C.dim })
      K.text(L('repo'), MX, 820, { size: 30, weight: 500, fam: 'mono', color: C.dim })
      K.label(L('deployed'), MX, 900, { size: 24 })
      metricValue(K, M('deploy.url'), MX + 200, 910, { size: 40, fam: 'mono' })
    })
    // the evaluation dimensions, drawn last: ink-grey while the yellow field owns the top of the frame
    const yellow = inOutCubic(gk) * (1 - fold)
    dims(K, L('dims'), outCubic(seg(t, 0.3, 0.8)) * (1 - yellow), C.mute)
    dims(K, L('dims'), yellow, C.inkDim)
  },
})
