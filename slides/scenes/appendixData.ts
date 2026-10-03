/**
 * Appendix: the data story (phases 03 and 04), for the data-engineering and
 * analytics criteria.
 *
 *   arrive  the problems the organizers announced: each one is measured and
 *           comes back zero, and is struck out
 *   1       the problems profiling found instead, each with its mechanism:
 *           a broken branch link, a complaint pointing at another customer's
 *           product, a wall of transcripts collapsing to a few texts, which is
 *           why the router learns from team-written utterances
 *   2       the historical cost per resolved contact, labeled a projection
 */
import { defineScene } from '../lib/scene/types'
import { C, MX } from '../lib/scene/kit'
import { clamp, hash, inOutCubic, lerp, outCubic, outExpo, presence, seg } from '../lib/scene/math'
import { source } from '../lib/scene/bank'
import { ring } from '../lib/scene/fx'

const WF = ['account_inquiry', 'card_support', 'dispute', 'credit'] as const
const CUES = [3.2, 7.0, 10.0] as const

export default defineScene({
  cues: CUES,
  draw({ t, L, M, K }) {
    K.label(L('eyebrow'), MX, 66, { size: 22, alpha: outCubic(seg(t, 0.1, 0.4)) })
    const c1 = CUES[0] + 0.05
    const c2 = CUES[1] + 0.05

    // ── arrive: announced, measured, absent ───────────────────────────────
    K.title(L('t0'), t, 0.1, { tout: c1 })
    K.fade(presence(t, 0.2, c1, 0.3, 0.25), () => {
      ;(['duplicates', 'late_partitions', 'schema_events'] as const).forEach((k, i) => {
        const y = 380 + i * 170
        const t0 = 0.4 + i * 0.35
        K.fade(outCubic(seg(t, t0, t0 + 0.3)), () => {
          K.label(L('announced'), MX, y - 46, { size: 22 })
          K.text(L(k), MX, y, { size: 44, weight: 700, fam: 'display' })
        })
        const w = K.measure(L(k), 44, 700, 'display')
        const sk = outCubic(seg(t, t0 + 0.9, t0 + 1.2))
        if (sk > 0) K.line(MX - 8, y - 14, MX - 8 + (w + 16) * sk, y - 14, C.red, 5)
        const m = M(`data.${k}`)
        K.fade(outCubic(seg(t, t0 + 0.6, t0 + 0.9)), () => {
          K.text(m.text, 1100, y + (1 - outExpo(seg(t, t0 + 0.6, t0 + 1.0))) * 30, { size: 72, weight: 800, fam: 'display' })
          K.label(L('found'), 1200, y - 10, { size: 22 })
        })
      })
      source(K, M('data.duplicates'), outCubic(seg(t, 1.6, 2.0)))
    })

    // ── 1 what profiling found instead ────────────────────────────────────
    K.title(L('t1'), t, c1 + 0.1, { tout: c2 })
    K.fade(presence(t, c1 + 0.1, c2, 0.3, 0.25), () => {
      const rows = [['data.orphan_branch_refs', 'q1'], ['data.complaint_foreign_product', 'q2'], ['data.transcript_texts', 'q3']] as const
      rows.forEach(([key, q], i) => {
        const y = 360 + i * 190
        const t0 = c1 + 0.3 + i * 0.45
        const k = outExpo(seg(t, t0, t0 + 0.6))
        K.fade(clamp(k * 2), () => {
          K.text(M(key).text, MX, y + (1 - k) * 24, { size: 52, weight: 800, fam: 'display' })
          K.text(L(q), MX, y + 46, { size: 28, weight: 500 })
          K.text(L(`${q}h`), MX, y + 84, { size: 24, weight: 500, color: C.dim })
        })
        // the mechanism, drawn at the right of each finding
        const gx = 1320
        const mk = seg(t, t0 + 0.3, t0 + 1.1)
        if (i === 0) {
          K.fade(outCubic(mk), () => {
            K.dot(gx, y, 14, C.paper)
            K.line(gx + 18, y, gx + 18 + 240 * outCubic(mk), y, C.paper, 3, [10, 8])
            K.ctx.save()
            K.ctx.setLineDash([6, 6])
            K.strokeRR(gx + 270, y - 26, 52, 52, 8, C.mute, 2)
            K.ctx.restore()
          })
          ring(K, gx + 296, y, seg(t, t0 + 1.0, t0 + 1.5), C.red, 8, 50)
        }
        else if (i === 1) {
          K.fade(outCubic(mk), () => {
            K.dot(gx, y - 20, 14, C.paper)
            K.dot(gx + 300, y + 20, 14, C.mute)
            K.arrow(gx + 20, y - 16, gx + 20 + 260 * outCubic(mk), y + 16, { color: C.red, lw: 3, head: 12 })
          })
        }
        else {
          const col = inOutCubic(seg(t, t0 + 0.6, t0 + 1.3))
          for (let j = 0; j < 12; j++) {
            const a = outCubic(seg(t, t0 + j * 0.02, t0 + 0.3 + j * 0.02)) * 0.5
            K.fade(a, () => K.fillRR(gx, lerp(y - 66 + j * 12, j % 2 ? y + 8 : y - 12, col), 160 + hash(j, 9) * 200, 6, 3, C.paper))
          }
        }
      })
      K.punch(L('punch'), t, c1 + 2.4, { y: 960, size: 36, accent: C.blueText })
      source(K, M('data.orphan_branch_refs'), outCubic(seg(t, c1 + 1.0, c1 + 1.4)), undefined)
    })

    // ── 2 cost per resolved contact, projected ────────────────────────────
    K.title(L('costTitle'), t, c2 + 0.1)
    K.fade(outCubic(seg(t, c2, c2 + 0.3)), () => {
      const max = Math.max(...WF.map((w) => M(`cost_resolved.${w}`).num))
      WF.forEach((w, i) => {
        const m = M(`cost_resolved.${w}`)
        const k = outExpo(seg(t, c2 + 0.3 + i * 0.15, c2 + 1.1 + i * 0.15))
        const y = 350 + i * 110
        const bw = 1000 * (m.num / max) * k
        K.fade(clamp(k * 3), () => {
          K.text(L(w), MX, y + 38, { size: 30, weight: 500 })
          K.fillRR(520, y, bw, 52, 4, w === 'dispute' ? C.red : C.paper)
          K.text(m.text, 520 + bw + 20, y + 40, { size: 36, weight: 700, fam: 'display' })
        })
      })
      K.fade(outCubic(seg(t, c2 + 1.5, c2 + 1.9)), () =>
        K.wrap(L('costNote'), 1400, 28, 500).forEach((ln, i) => K.text(ln, MX, 850 + i * 38, { size: 28, weight: 500, color: C.dim })))
      source(K, M('cost_resolved.dispute'), outCubic(seg(t, c2 + 1.5, c2 + 1.9)), 'data_platform/analysis/cost_assumptions.yaml')
    })
  },
})
