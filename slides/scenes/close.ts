/**
 * Slide 6, honest limits, the route to operation, the team, the close.
 *
 *   arrive  what we cannot claim yet (red markers: risk)
 *   1       the route to operation: in place (yellow) and remaining
 *   2       the team, with the roles the team gave itself
 *   3       the thesis, the repository, and the deployment link (pending)
 */
import { defineScene } from '../lib/scene/types'
import { C, MX } from '../lib/scene/kit'
import { clamp, outCubic, outExpo, presence, seg } from '../lib/scene/math'
import { metricValue } from '../lib/scene/bank'

export default defineScene({
  cues: [2.8, 5.8, 8.4, 10.8],
  draw({ t, L, M, K }) {
    const heading = (key: string, t0: number, tout?: number) =>
      K.words(L(key), MX, 150, { t, t0, tout, size: 56, weight: 700, fam: 'display' })
    const item = (s: string, x: number, y: number, t0: number, marker: () => void, size = 32, maxW = 1560) => {
      const k = outExpo(seg(t, t0, t0 + 0.6))
      K.fade(clamp(k * 2), () => {
        const dy = (1 - k) * 20
        K.ctx.save()
        K.ctx.translate(0, dy)
        marker()
        K.wrap(s, maxW, size, 500).forEach((ln, i) => K.text(ln, x + 36, y + i * size * 1.3, { size, weight: 500 }))
        K.ctx.restore()
      })
    }

    // ── arrive: limits ───────────────────────────────────────────────────
    heading('limitsTitle', 0.1, 2.85)
    K.fade(presence(t, 0.2, 2.85, 0.3, 0.25), () => {
      for (let i = 0; i < 5; i++) {
        const y = 340 + i * 110
        item(L(`l${i + 1}`), MX, y, 0.5 + i * 0.25, () => K.fillRR(MX, y - 14, 18, 5, 2, C.red), 34)
      }
      K.cite(L('cite'), outCubic(seg(t, 1.6, 2.0)))
    })

    // ── 1 route to operation ─────────────────────────────────────────────
    heading('routeTitle', 3.0, 5.85)
    K.fade(presence(t, 2.9, 5.85, 0.3, 0.25), () => {
      K.label(L('inPlace'), MX, 320, { size: 24, color: C.yellow, alpha: outCubic(seg(t, 3.2, 3.5)) })
      K.label(L('remaining'), 1000, 320, { size: 24, color: C.dim, alpha: outCubic(seg(t, 3.9, 4.2)) })
      for (let i = 0; i < 5; i++) {
        const y = 400 + i * 84
        item(L(`i${i + 1}`), MX, y, 3.3 + i * 0.12, () => K.fillRR(MX, y - 14, 18, 5, 2, C.yellow), 30, 760)
        item(L(`r${i + 1}`), 1000, y, 4.0 + i * 0.12, () => K.strokeRR(1000, y - 20, 16, 16, 3, C.dim, 2), 30, 760)
      }
      K.fade(outCubic(seg(t, 4.8, 5.2)), () => {
        K.label(L('deployed'), 1000, 860, { size: 24 })
        metricValue(K, M('deploy.url'), 1200, 870, { size: 40, fam: 'mono' })
      })
    })

    // ── 2 team ───────────────────────────────────────────────────────────
    K.fade(presence(t, 5.9, 8.45, 0.3, 0.25), () => {
      K.words(L('teamTitle'), MX, 380, { t, t0: 6.0, size: 96, weight: 800, fam: 'display', stagger: 0.05 })
      for (let i = 0; i < 4; i++) {
        const x = i % 2 ? 1000 : MX
        const y = 590 + Math.floor(i / 2) * 190
        const k = outExpo(seg(t, 6.5 + i * 0.15, 7.2 + i * 0.15))
        K.fade(clamp(k * 2), () => {
          K.text(L(`m${i + 1}`), x, y + (1 - k) * 24, { size: 52, weight: 700, fam: 'display' })
          K.text(L(`m${i + 1}r`), x, y + 52 + (1 - k) * 24, { size: 28, weight: 500, fam: 'mono', color: C.dim })
        })
      }
    })

    // ── 3 close ──────────────────────────────────────────────────────────
    const lines = [['c1', C.blue], ['c2', C.yellow], ['c3', C.paper]] as const
    lines.forEach(([key, accent], i) =>
      K.words(L(key), MX, 400 + i * 120, { t, t0: 8.6 + i * 0.35, size: 80, weight: 800, fam: 'display', accent, stagger: 0.05 }))
    K.fade(outCubic(seg(t, 9.8, 10.2)), () => {
      K.text(L('repo'), MX, 800, { size: 30, weight: 500, fam: 'mono', color: C.dim })
      K.label(L('deployed'), MX, 880, { size: 24 })
      metricValue(K, M('deploy.url'), 320, 890, { size: 40, fam: 'mono' })
    })
  },
})
