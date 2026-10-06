/**
 * Pitch slide 5 (static): the evidence, per workflow first.
 *
 *   left    safe automated resolution per workflow for P, B0 and B1, with
 *           Wilson intervals and denominators; below, the trade-offs (missed
 *           and unnecessary transfers, latency)
 *   right   the aggregate over the four workflows, then unsafe outcomes
 *
 * Every number is from data/metrics.yml (docs/evaluation/results.md), a
 * simulation on a hosted model, labeled as such.
 */
import { defineScene } from '../lib/scene/types'
import { C, MX, type Kit } from '../lib/scene/kit'
import { KIND_LABEL, type Metric } from '../lib/metrics'
import { dims } from '../lib/scene/bank'
import { SYS, SYS_MAIN, SYS_TEXT, WF, sysTab } from './parts/evidence-rates'
import { S, citeFit, ptitle } from './parts/pitch-kit'

const X0 = 420
const X1 = 860
const sx = (v: number) => X0 + ((X1 - X0) * v) / 100
const COL = [940, 1040, 1140] as const
const RX = 1240

function interval(K: Kit, m: Metric, y: number, i: number, h = 8) {
  if (m.pending) return
  K.fillRR(sx(m.lo), y - h / 2, Math.max(h, sx(m.hi) - sx(m.lo)), h, h / 2, SYS_MAIN[i])
  K.dot(sx(m.num), y, h * 1.2, SYS_MAIN[i])
  K.dot(sx(m.num), y, h * 0.55, C.bg)
}

export default defineScene({
  cues: [30],
  draw({ L, M, K }) {
    const E = S.evidence
    dims(K, E('dims'))
    ptitle(K, E('t0'))
    K.label(`${M('eval.cases').text} ${E('casesLbl')}  |  ${E('casesSub')}`, MX, 226, { size: 22, color: C.dim })

    // the three systems
    ;[0, 1, 2].forEach((i) => {
      const x = MX + i * 560
      const w = sysTab(K, E, i, x + 30, 252, 1, 22)
      K.text(E(`name${i}`), x + 30 + w / 2 + 16, 280, { size: 26, weight: 600 })
      K.label(E(`model${i}`), x + 30 + w / 2 + 16, 310, { size: 20 })
    })
    K.line(MX, 340, 1800, 340, C.faint, 2)

    // ── left: per workflow first ──────────────────────────────────────────
    K.label(E('t1'), MX, 380, { size: 22, color: C.paper, weight: 600 })
    K.label(L('perSub'), MX, 408, { size: 20 })
    SYS.forEach((_, i) => sysTab(K, E, i, COL[i], 378, 1, 20))
    WF.forEach((w, r) => {
      const y = 470 + r * 86
      K.text(E(w), MX, y + 9, { size: 26, weight: 600 })
      K.line(X0, y + 40, 1180, y + 40, C.rail, 2)
      SYS.forEach((s, i) => {
        const m = M(`eval.sar.${w}.${s}`)
        interval(K, m, y - 22 + i * 22, i)
        K.text(m.text, COL[i], y + 9, { size: 22, weight: 500, fam: 'mono', color: SYS_TEXT[i], align: 'center' })
      })
      if (M(`eval.sar.${w}.p`).num < M(`eval.sar.${w}.b0`).num) {
        K.fillRR(MX - 30, y - 30, 8, 60, 4, C.red)
        K.label(E('notAhead'), MX, y + 34, { size: 20, color: C.redText })
      }
    })
    K.label(E('intervalNote'), X0, 832, { size: 20 })

    // the trade-offs, same columns
    const rows = ['missed', 'unnecessary', 'latency_p50'] as const
    rows.forEach((fam, r) => {
      const y = 884 + r * 44
      K.text(E(fam), MX, y, { size: 24, weight: 500 })
      SYS.forEach((s, i) => K.text(M(`eval.${fam}.${s}`).text, COL[i], y, { size: 22, weight: 500, fam: 'mono', color: SYS_TEXT[i], align: 'center' }))
    })

    // ── right: the aggregate, then unsafe outcomes ────────────────────────
    K.line(1200, 360, 1200, 980, C.faint, 2)
    K.label(E('t2'), RX, 380, { size: 22, color: C.paper, weight: 600 })
    K.label(E('sarShort'), RX, 408, { size: 20 })
    SYS.forEach((s, i) => {
      const m = M(`eval.sar.all.${s}`)
      const y = 492 + i * 84
      K.text(`${Math.round(m.num)}%`, RX, y, { size: 64, weight: 800, fam: 'display', color: SYS_TEXT[i] })
      sysTab(K, E, i, RX + 270, y - 40, 1, 20)
      K.text(m.text, RX + 330, y - 12, { size: 22, weight: 500, fam: 'mono', color: SYS_TEXT[i] })
      K.label(`${m.lo} ${E('to')} ${m.hi}%`, RX + 330, y + 16, { size: 20 })
    })

    K.label(E('t3'), RX, 748, { size: 22, color: C.paper, weight: 600 })
    SYS.forEach((s, i) => {
      const m = M(`eval.unsafe.${s}`)
      const y = 806 + i * 60
      sysTab(K, E, i, RX + 30, y - 30, 1, 20)
      K.text(m.text, RX + 80, y, { size: 36, weight: 700, fam: 'display', color: s === 'b1' ? C.red : C.paper })
    })
    K.label(`${E('sys2')}: ${M('eval.b1.credit_cases').text} ${E('inCredit')}`, RX, 990, { size: 20 })

    const m = M('eval.sar.all.p')
    citeFit(K, `${KIND_LABEL[m.kind]} ${E('onModel')}  |  ${m.source}  |  ${E('run')}`)
  },
})
