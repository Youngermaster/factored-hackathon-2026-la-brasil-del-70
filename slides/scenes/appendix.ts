/**
 * Appendix, for the data-engineering and analytics criteria.
 *
 *   arrive  three profiling findings and how the pipeline handles each
 *   1       the historical cost per resolved contact, labeled a projection
 */
import { defineScene } from '../lib/scene/types'
import { C, MX } from '../lib/scene/kit'
import { clamp, outCubic, outExpo, presence, seg } from '../lib/scene/math'
import { source } from '../lib/scene/bank'

const WF = ['account_inquiry', 'card_support', 'dispute', 'credit'] as const

export default defineScene({
  cues: [3.0, 6.0],
  draw({ t, L, M, K }) {
    K.label(L('eyebrow'), MX, 66, { size: 22, alpha: outCubic(seg(t, 0.1, 0.4)) })

    // ── arrive: profiling findings ────────────────────────────────────────
    K.words(L('title'), MX, 150, { t, t0: 0.1, tout: 3.05, size: 56, weight: 700, fam: 'display' })
    K.fade(presence(t, 0.2, 3.05, 0.3, 0.25), () => {
      const rows = [
        ['data.orphan_branch_refs', 'q1'],
        ['data.complaint_foreign_product', 'q2'],
        ['data.rows_quarantined', 'q3'],
      ] as const
      rows.forEach(([key, q], i) => {
        const y = 360 + i * 200
        const k = outExpo(seg(t, 0.5 + i * 0.3, 1.2 + i * 0.3))
        K.fade(clamp(k * 2), () => {
          K.text(M(key).text, MX, y + (1 - k) * 24, { size: 60, weight: 700, fam: 'display' })
          K.text(L(q), MX, y + 50, { size: 30, weight: 500 })
          K.text(L(`${q}h`), MX, y + 90, { size: 26, weight: 500, color: C.dim })
        })
      })
      source(K, M('data.orphan_branch_refs'), outCubic(seg(t, 1.6, 2.0)))
    })

    // ── 1 cost per resolved contact, projected ────────────────────────────
    K.words(L('costTitle'), MX, 150, { t, t0: 3.2, size: 56, weight: 700, fam: 'display' })
    K.fade(outCubic(seg(t, 3.1, 3.4)), () => {
      const max = Math.max(...WF.map((w) => M(`cost_resolved.${w}`).num))
      WF.forEach((w, i) => {
        const m = M(`cost_resolved.${w}`)
        const k = outExpo(seg(t, 3.4 + i * 0.15, 4.2 + i * 0.15))
        const y = 350 + i * 110
        const bw = 1000 * (m.num / max) * k
        K.fade(clamp(k * 3), () => {
          K.text(L(w), MX, y + 38, { size: 30, weight: 500 })
          K.fillRR(520, y, bw, 52, 4, w === 'dispute' ? C.red : C.paper)
          K.text(m.text, 520 + bw + 20, y + 40, { size: 36, weight: 700, fam: 'display' })
        })
      })
      K.fade(outCubic(seg(t, 4.6, 5.0)), () =>
        K.wrap(L('costNote'), 1400, 28, 500).forEach((ln, i) => K.text(ln, MX, 850 + i * 38, { size: 28, weight: 500, color: C.dim })))
      source(K, M('cost_resolved.dispute'), outCubic(seg(t, 4.6, 5.0)), 'data_platform/analysis/cost_assumptions.yaml')
    })
  },
})
