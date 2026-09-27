/**
 * Slide 5, evidence: the evaluation method and its results.
 *
 *   arrive  the workload fills in: 4 workflows x 2 languages x 3 paths, each
 *           cell in its path colour, the same cases for B0 and the system
 *   1       the brief's stress cases fly into the matrix and mark its cells
 *   2       the four outcome definitions, system against B0 (pending)
 *   3       safe automated resolution per workflow and language (pending)
 *   4       efficiency (pending) and, on a blue field, retrieval: the learned
 *           component measured so far, provisional
 *
 * Every result reads data/metrics.yml; until phase 14 reports, the values
 * render as dashed "pending" boxes and `pnpm check:content --strict` fails.
 */
import { defineScene } from '../lib/scene/types'
import { C, H, MX } from '../lib/scene/kit'
import { clamp, hash, outCubic, outExpo, presence, seg } from '../lib/scene/math'
import { metricValue, tab } from '../lib/scene/bank'
import { KIND_LABEL } from '../lib/metrics'
import { field, packet } from '../lib/scene/fx'

const WF = ['account_inquiry', 'card_support', 'dispute', 'credit'] as const
const PATH = [C.yellow, C.blue, C.red] as const
const CX = 440
const cellX = (c: number) => CX + c * 70 + (c >= 3 ? 30 : 0)
const cellY = (r: number) => 420 + r * 90

export default defineScene({
  cues: [2.4, 5.2, 8.2, 11.0, 14.2],
  draw({ t, L, M, K }) {
    K.title(L('title'), t, 0.1, { tout: 11.05 })

    // ── arrive + 1: the workload matrix, then the stress cases ────────────
    K.fade(presence(t, 0.2, 5.3, 0.3, 0.25), () => {
      WF.forEach((w, r) => {
        K.label(L(w), MX, cellY(r) + 36, { size: 24, color: C.dim, alpha: outCubic(seg(t, 0.3 + r * 0.08, 0.7 + r * 0.08)) })
        for (let c = 0; c < 6; c++) {
          const k = seg(t, 0.5 + (r * 6 + c) * 0.03, 0.9 + (r * 6 + c) * 0.03)
          field(K, cellX(c), cellY(r), 56, 56, PATH[c % 3], k, 'bottom', 8)
          // 1: a stress case lands on some cells and leaves an ink notch
          if (hash(r, c) < 0.45) {
            const land = seg(t, 3.2 + hash(c, r) * 0.9, 3.5 + hash(c, r) * 0.9)
            if (land >= 1) K.fillRR(cellX(c) + 36, cellY(r) + 6, 14, 14, 3, C.bg)
          }
        }
      })
      K.fade(outCubic(seg(t, 1.2, 1.6)), () => {
        K.text('es', CX + 98, 395, { size: 26, weight: 600, fam: 'mono', align: 'center' })
        K.text('pt', CX + 338, 395, { size: 26, weight: 600, fam: 'mono', align: 'center' })
        K.label(L('legend'), CX, 820, { size: 22 })
      })
      K.fade(outCubic(seg(t, 1.3, 1.8)), () => {
        K.text(L('same'), 1000, 440, { size: 36, weight: 600 })
        K.text(L('b0'), 1000, 494, { size: 28, weight: 500, color: C.dim })
      })
      K.fade(presence(t, 1.8, 2.5, 0.3, 0.2), () => {
        metricValue(K, M('eval.cases'), 1000, 640, { size: 48 })
        K.label(L('cases'), 1000, 680, { size: 22 })
      })
      // the stress tags, then packets from each tag into the matrix
      K.fade(outCubic(seg(t, 2.6, 2.9)), () => K.label(L('stress'), 1000, 600, { size: 24, color: C.redText }))
      for (let i = 0; i < 6; i++) {
        const x = 1000 + (i % 2) * 380
        const y = 630 + Math.floor(i / 2) * 64
        tab(K, L(`f${i + 1}`), x, y, { tone: 'red', k: seg(t, 2.7 + i * 0.1, 3.1 + i * 0.1), size: 24 })
        for (let j = 0; j < 2; j++) {
          const r = Math.floor(hash(i, j + 7) * 4)
          const c = Math.floor(hash(j, i + 3) * 6)
          packet(K, [{ x: x + 10, y: y + 20 }, { x: cellX(c) + 43, y: cellY(r) + 13 }], seg(t, 3.2 + i * 0.12 + j * 0.2, 3.9 + i * 0.12 + j * 0.2), C.red, 8)
        }
      }
    })

    // ── 2 outcomes: four tiles, system against B0 ─────────────────────────
    K.fade(presence(t, 5.3, 8.25, 0.3, 0.25), () => {
      const tiles: [string, string, [string, string][], string | null][] = [
        ['m_safe', C.yellow, [['eval.safe_resolution', 'sys'], ['eval.safe_resolution.b0', 'base'], ['eval.attempted', 'attempted']], null],
        ['m_contain', C.paper, [['eval.containment', 'sys'], ['eval.containment.b0', 'base']], 'm_containNote'],
        ['m_escal', C.red, [['eval.missed_escalations', 'missed'], ['eval.unneeded_escalations', 'unneeded']], null],
        ['m_unsafe', C.red, [['eval.unsafe', 'sys'], ['eval.unsafe.b0', 'base']], null],
      ]
      tiles.forEach(([lbl, color, vals, note], i) => {
        const x = MX + (i % 2) * 850
        const y = 290 + Math.floor(i / 2) * 330
        const k = seg(t, 5.5 + i * 0.15, 6.1 + i * 0.15)
        field(K, x, y, 810, 290, C.bg2, k, 'bottom', 12)
        field(K, x, y, 810, 10, color, seg(t, 5.8 + i * 0.15, 6.3 + i * 0.15), 'left', 5)
        K.fade(outCubic(seg(t, 5.9 + i * 0.15, 6.3 + i * 0.15)), () => {
          K.text(L(lbl), x + 36, y + 76, { size: 34, weight: 600 })
          if (note) K.label(L(note), x + 36, y + 112, { size: 22 })
          vals.forEach(([key, who], j) => {
            metricValue(K, M(key), x + 36 + j * 250, y + 222, { size: 40 })
            K.label(L(who), x + 36 + j * 250, y + 258, { size: 22 })
          })
        })
      })
      K.cite(L('cite'))
    })

    // ── 3 per workflow and language ────────────────────────────────────────
    K.fade(presence(t, 8.3, 11.05, 0.3, 0.25), () => {
      K.words(L('gridH'), MX, 300, { t, t0: 8.4, size: 40, weight: 700, fam: 'display', stagger: 0.02 })
      K.fade(outCubic(seg(t, 8.6, 8.9)), () => {
        K.text('es', 760, 400, { size: 28, weight: 700, fam: 'mono' })
        K.text('pt', 1060, 400, { size: 28, weight: 700, fam: 'mono' })
      })
      WF.forEach((w, r) => {
        const y = 440 + r * 104
        field(K, MX, y, 560, 80, C.paper, seg(t, 8.7 + r * 0.1, 9.2 + r * 0.1), 'left', 10)
        K.fade(outCubic(seg(t, 8.9 + r * 0.1, 9.3 + r * 0.1)), () => {
          K.text(L(w), MX + 28, y + 52, { size: 32, weight: 700, fam: 'display', color: C.bg })
          metricValue(K, M(`eval.sar.${w}.es`), 760, y + 58, { size: 40 })
          metricValue(K, M(`eval.sar.${w}.pt`), 1060, y + 58, { size: 40 })
        })
      })
      K.fade(outCubic(seg(t, 9.6, 10.0)), () => K.text(L('gridNote'), 1380, 500, { size: 30, weight: 500, color: C.dim }))
      K.cite(L('cite'))
    })

    // ── 4 efficiency, and retrieval on a blue field ────────────────────────
    K.fade(outCubic(seg(t, 11.1, 11.4)), () => {
      K.words(L('effH'), MX, 330, { t, t0: 11.2, size: 36, weight: 700, fam: 'display', stagger: 0.02 })
      const eff: [string, string, boolean][] = [['e_p50', 'eval.latency_p50', false], ['e_p95', 'eval.latency_p95', false], ['e_costA', 'eval.cost_attempted', true], ['e_costR', 'eval.cost_resolved', true]]
      eff.forEach(([lbl, key, proj], i) => {
        const y = 440 + i * 110
        K.fade(outCubic(seg(t, 11.4 + i * 0.12, 11.8 + i * 0.12)), () => {
          K.text(L(lbl), MX, y, { size: 30, weight: 500 })
          if (proj) K.label(L('projection'), MX, y + 32, { size: 22 })
          metricValue(K, M(key), 560, y + 8, { size: 40 })
        })
      })
    })
    field(K, 960, -4, 964, H + 8, C.blue, seg(t, 11.9, 12.5), 'right')
    K.fade(outCubic(seg(t, 12.3, 12.6)), () => {
      K.words(L('retH'), 1040, 330, { t, t0: 12.3, size: 40, weight: 700, fam: 'display', color: C.bg, stagger: 0.02 })
      K.text(L('r1'), 1040, 410, { size: 24, weight: 600, fam: 'mono', color: C.bg })
    })
    ;(['bm25', 'dense', 'hybrid'] as const).forEach((r, i) => {
      const m = M(`retrieval.r1.${r}`)
      const k = outExpo(seg(t, 12.5 + i * 0.15, 13.2 + i * 0.15))
      const y = 450 + i * 76
      K.fade(clamp(k * 3), () => {
        K.text(r, 1040, y + 32, { size: 26, weight: 600, fam: 'mono', color: C.bg })
        K.fillRR(1170, y + 6, 520 * m.num * k, 40, 6, C.bg)
        K.text(m.text, 1170 + 520 * m.num * k + 16, y + 36, { size: 30, weight: 800, fam: 'display', color: C.bg })
      })
    })
    K.fade(outCubic(seg(t, 13.3, 13.7)), () => {
      K.text(`${M('retrieval.abst_p.hybrid').text} / ${M('retrieval.abst_r.hybrid').text}`, 1040, 760, { size: 44, weight: 800, fam: 'display', color: C.bg })
      K.text(L('abst'), 1040, 800, { size: 24, weight: 600, fam: 'mono', color: C.bg })
      K.text(M('retrieval.p95.hybrid').text, 1520, 760, { size: 44, weight: 800, fam: 'display', color: C.bg })
      K.text(L('p95'), 1520, 800, { size: 24, weight: 600, fam: 'mono', color: C.bg })
      const r1 = M('retrieval.r1.hybrid')
      const cite = `${KIND_LABEL[r1.kind]}  |  ${r1.source}  |  ${M('retrieval.test_queries').text} ${L('retNote')}`
      K.wrap(cite, 800, 22, 500, 'mono').forEach((ln, i) => K.text(ln, 1040, H - 78 + i * 30, { size: 22, weight: 500, fam: 'mono', color: C.bg }))
    })
  },
})
