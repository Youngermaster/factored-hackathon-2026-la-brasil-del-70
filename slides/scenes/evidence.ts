/**
 * Slide 5, evidence: the evaluation method and its results.
 *
 *   arrive  the workload: 4 workflows x 2 languages x 3 paths, the same cases
 *           for baseline B0 and the system
 *   1       the stress cases from the brief, held out
 *   2       the brief's outcome definitions, system against B0
 *   3       safe automated resolution per workflow and language
 *   4       efficiency (pending), and the one learned component measured so
 *           far: retrieval, provisional
 *
 * Every result reads data/metrics.yml; until phase 14 reports, the values
 * render as dashed "pending" boxes and `pnpm check:content --strict` fails.
 */
import { defineScene } from '../lib/scene/types'
import { C, MX } from '../lib/scene/kit'
import { clamp, outCubic, outExpo, presence, seg } from '../lib/scene/math'
import { metricValue, source, tag } from '../lib/scene/bank'

const WF = ['account_inquiry', 'card_support', 'dispute', 'credit'] as const
const PATH = [C.yellow, C.blue, C.red] as const

export default defineScene({
  cues: [2.4, 5.2, 8.2, 11.0, 14.2],
  draw({ t, L, M, K }) {
    K.title(L('title'), t, 0.1)

    // ── arrive + 1: the workload matrix and the stress cases ──────────────
    K.fade(presence(t, 0.2, 5.3, 0.3, 0.25), () => {
      const CX = 440
      WF.forEach((w, r) => {
        const y = 420 + r * 90
        K.label(L(w), MX, y + 36, { size: 24, color: C.dim, alpha: outCubic(seg(t, 0.3 + r * 0.08, 0.7 + r * 0.08)) })
        for (let c = 0; c < 6; c++) {
          const x = CX + c * 70 + (c >= 3 ? 30 : 0)
          const k = outExpo(seg(t, 0.5 + (r * 6 + c) * 0.03, 0.9 + (r * 6 + c) * 0.03))
          if (k <= 0) continue
          K.fade(k, () => {
            K.fillRR(x, y + (1 - k) * 16, 56, 56, 6, C.bg2)
            K.fillRR(x, y + (1 - k) * 16, 56, 5, 2, PATH[c % 3])
          })
        }
      })
      K.fade(outCubic(seg(t, 1.2, 1.6)), () => {
        K.text('es', CX + 98, 395, { size: 26, weight: 600, fam: 'mono', align: 'center' })
        K.text('pt', CX + 338, 395, { size: 26, weight: 600, fam: 'mono', align: 'center' })
        K.label(L('legend'), CX, 820, { size: 22 })
      })
      K.fade(outCubic(seg(t, 1.3, 1.8)), () => {
        K.wrap(L('same'), 760, 36, 600).forEach((ln, i) => K.text(ln, 1000, 440 + i * 46, { size: 36, weight: 600 }))
        K.wrap(L('b0'), 760, 26, 500).forEach((ln, i) => K.text(ln, 1000, 560 + i * 34, { size: 26, weight: 500, color: C.dim }))
      })
      // 1: the stress cases replace the workload note
      K.fade(presence(t, 1.8, 2.5, 0.3, 0.2), () => {
        metricValue(K, M('eval.cases'), 1000, 720, { size: 48 })
        K.label(L('cases'), 1000, 760, { size: 22 })
      })
      K.fade(outCubic(seg(t, 2.6, 2.9)), () => {
        K.label(L('stress'), 1000, 690, { size: 24, color: C.redText })
        for (let i = 0; i < 6; i++)
          tag(K, L(`f${i + 1}`), 1000 + (i % 2) * 360, 720 + Math.floor(i / 2) * 62, { tone: 'red', k: seg(t, 2.8 + i * 0.12, 3.2 + i * 0.12), size: 24 })
      })
    })

    // ── 2 outcomes: system against B0 ─────────────────────────────────────
    K.fade(presence(t, 5.3, 8.25, 0.3, 0.25), () => {
      const VX = 1180
      const BX = 1520
      K.fade(outCubic(seg(t, 5.4, 5.7)), () => {
        K.label(L('sys'), VX, 330, { size: 24, color: C.dim })
        K.label(L('base'), BX, 330, { size: 24, color: C.dim })
      })
      const rows: [string, string | null, string | null, string | null][] = [
        ['m_safe', 'eval.safe_resolution', 'eval.safe_resolution.b0', null],
        ['m_attempted', 'eval.attempted', null, null],
        ['m_contain', 'eval.containment', 'eval.containment.b0', 'm_containNote'],
        ['m_missed', 'eval.missed_escalations', null, null],
        ['m_unneeded', 'eval.unneeded_escalations', null, null],
        ['m_unsafe', 'eval.unsafe', 'eval.unsafe.b0', null],
      ]
      rows.forEach(([lbl, sys, base, note], i) => {
        const y = 430 + i * 92
        const k = outCubic(seg(t, 5.6 + i * 0.12, 6.0 + i * 0.12))
        K.fade(k, () => {
          K.text(L(lbl), MX, y, { size: 32, weight: 500 })
          if (note) K.label(L(note), MX, y + 32, { size: 22 })
          if (sys) metricValue(K, M(sys), VX, y + 8, { size: 40 })
          if (base) metricValue(K, M(base), BX, y + 8, { size: 40 })
        })
      })
      K.cite(L('cite'))
    })

    // ── 3 per workflow and language ────────────────────────────────────────
    K.fade(presence(t, 8.3, 11.05, 0.3, 0.25), () => {
      K.words(L('gridH'), MX, 330, { t, t0: 8.4, size: 36, weight: 700, fam: 'display', stagger: 0.02 })
      K.fade(outCubic(seg(t, 8.6, 8.9)), () => {
        K.text('es', 760, 430, { size: 26, weight: 600, fam: 'mono' })
        K.text('pt', 1060, 430, { size: 26, weight: 600, fam: 'mono' })
      })
      WF.forEach((w, r) => {
        const y = 520 + r * 96
        K.fade(outCubic(seg(t, 8.8 + r * 0.12, 9.2 + r * 0.12)), () => {
          K.text(L(w), MX, y, { size: 32, weight: 500 })
          metricValue(K, M(`eval.sar.${w}.es`), 760, y + 8, { size: 40 })
          metricValue(K, M(`eval.sar.${w}.pt`), 1060, y + 8, { size: 40 })
        })
      })
      K.fade(outCubic(seg(t, 9.6, 10.0)), () =>
        K.wrap(L('gridNote'), 440, 26, 500).forEach((ln, i) => K.text(ln, 1380, 520 + i * 36, { size: 26, weight: 500, color: C.dim })))
      K.cite(L('cite'))
    })

    // ── 4 efficiency, and retrieval measured so far ────────────────────────
    K.fade(outCubic(seg(t, 11.1, 11.4)), () => {
      K.words(L('effH'), MX, 330, { t, t0: 11.2, size: 36, weight: 700, fam: 'display', stagger: 0.02 })
      const eff: [string, string, boolean][] = [['e_p50', 'eval.latency_p50', false], ['e_p95', 'eval.latency_p95', false], ['e_costA', 'eval.cost_attempted', true], ['e_costR', 'eval.cost_resolved', true]]
      eff.forEach(([lbl, key, proj], i) => {
        const y = 440 + i * 100
        K.fade(outCubic(seg(t, 11.4 + i * 0.12, 11.8 + i * 0.12)), () => {
          K.text(L(lbl), MX, y, { size: 30, weight: 500 })
          if (proj) K.label(L('projection'), MX, y + 32, { size: 22 })
          metricValue(K, M(key), 560, y + 8, { size: 40 })
        })
      })
      K.words(L('retH'), 1000, 330, { t, t0: 12.0, size: 36, weight: 700, fam: 'display', color: C.blueText, stagger: 0.02 })
      K.fade(outCubic(seg(t, 12.2, 12.5)), () => K.label(L('r1'), 1000, 410, { size: 22 }))
      ;(['bm25', 'dense', 'hybrid'] as const).forEach((r, i) => {
        const m = M(`retrieval.r1.${r}`)
        const k = outExpo(seg(t, 12.3 + i * 0.15, 13.0 + i * 0.15))
        const y = 450 + i * 70
        K.fade(clamp(k * 3), () => {
          K.text(r, 1000, y + 30, { size: 24, weight: 500, fam: 'mono', color: C.dim })
          K.fillRR(1130, y + 6, 560 * m.num * k, 34, 4, C.blue)
          K.text(m.text, 1130 + 560 * m.num * k + 16, y + 32, { size: 28, weight: 700, fam: 'display' })
        })
      })
      K.fade(outCubic(seg(t, 13.2, 13.6)), () => {
        K.text(`${M('retrieval.abst_p.hybrid').text} / ${M('retrieval.abst_r.hybrid').text}`, 1000, 740, { size: 40, weight: 700, fam: 'display' })
        K.label(L('abst'), 1000, 778, { size: 22 })
        K.text(M('retrieval.p95.hybrid').text, 1480, 740, { size: 40, weight: 700, fam: 'display' })
        K.label(L('p95'), 1480, 778, { size: 22 })
        source(K, M('retrieval.r1.hybrid'), 1, `${M('retrieval.test_queries').text} ${L('retNote')}`)
      })
    })
  },
})
