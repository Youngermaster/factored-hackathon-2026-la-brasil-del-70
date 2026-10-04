/**
 * Appendix: the rest of the phase 14b evidence, for questions.
 *
 *   arrive  consistency over repeated runs (pass^3) and the language slices,
 *           P, B0 and B1 in the colours of the evidence slide
 *   1       operating efficiency (measured latency, projected cost) and, on a
 *           blue field, retrieval: the learned component measured first,
 *           provisional
 */
import { defineScene } from '../lib/scene/types'
import { C, H, MX } from '../lib/scene/kit'
import { clamp, outCubic, outExpo, presence, seg } from '../lib/scene/math'
import { metricValue } from '../lib/scene/bank'
import { KIND_LABEL } from '../lib/metrics'
import { field } from '../lib/scene/fx'
import { SYS, SYS_MAIN, SYS_TEXT, sysTab } from './parts/evidence-rates'

const CUES = [3.2, 6.4] as const

export default defineScene({
  cues: CUES,
  draw({ t, L, M, K }) {
    K.label(L('eyebrow'), MX, 66, { size: 22, alpha: outCubic(seg(t, 0.1, 0.4)) })
    const c1 = CUES[0] + 0.05
    K.title(L('t0'), t, 0.1, { tout: c1 })

    // ── arrive: pass^3, then the language slices ──────────────────────────
    K.fade(presence(t, 0.2, c1, 0.3, 0.25), () => {
      K.label(L('passLbl'), MX, 280, { size: 24, color: C.dim })
      K.label(`${L('passLbl2')} ${M('eval.repeat_scenarios').text} ${L('passLbl3')}`, MX, 314, { size: 24, color: C.dim })
      SYS.forEach((s, i) => {
        const m = M(`eval.pass3.${s}`)
        const y = 370 + i * 90
        const k = outExpo(seg(t, 0.4 + i * 0.15, 1.2 + i * 0.15))
        sysTab(K, L, i, MX + 30, y, seg(t, 0.3 + i * 0.15, 0.7 + i * 0.15), 24)
        if (k > 0) K.fillRR(MX + 90, y + 6, 560 * (m.num / 100) * k, 28, 6, SYS_MAIN[i])
        K.fade(clamp(k * 3), () => K.text(m.text, MX + 90 + 560 * (m.num / 100) * k + 18, y + 32, { size: 36, weight: 800, fam: 'display', color: SYS_TEXT[i] }))
      })
      // language slices: es against pt for each system, with the intervals
      const LX = 1040
      K.fade(outCubic(seg(t, 1.2, 1.5)), () => K.label(L('langLbl'), LX, 280, { size: 24, color: C.dim }))
      ;(['es', 'pt'] as const).forEach((lang, r) => {
        const y = 380 + r * 170
        K.fade(outCubic(seg(t, 1.3 + r * 0.2, 1.6 + r * 0.2)), () => K.text(lang, LX, y + 10, { size: 32, weight: 700, fam: 'mono' }))
        SYS.forEach((s, i) => {
          const m = M(`eval.lang.${lang}.${s}`)
          const yy = y - 30 + i * 30
          const k = outExpo(seg(t, 1.5 + r * 0.2 + i * 0.1, 2.1 + r * 0.2 + i * 0.1))
          const X0 = LX + 80
          const sc = (v: number) => X0 + 5.2 * v
          if (k > 0) {
            const c = sc(m.num)
            K.fillRR(c - (c - sc(m.lo)) * k, yy - 5, Math.max(10, (sc(m.hi) - sc(m.lo)) * k), 10, 5, SYS_MAIN[i])
            K.dot(c, yy, 10, SYS_MAIN[i])
          }
          K.fade(outCubic(seg(t, 1.9 + r * 0.2 + i * 0.1, 2.2 + r * 0.2 + i * 0.1)), () =>
            K.text(m.text, LX + 640, yy + 8, { size: 22, weight: 500, fam: 'mono', color: SYS_TEXT[i], align: 'right' }))
        })
      })
      K.fade(outCubic(seg(t, 2.4, 2.8)), () => K.text(L('langNote'), LX, 760, { size: 28, weight: 500, color: C.dim }))
      K.cite(`${KIND_LABEL.simulation} ${L('onModel')}  |  docs/evaluation/results.md`, outCubic(seg(t, 1.0, 1.4)))
    })

    // ── 1 efficiency, and retrieval on a blue field ────────────────────────
    K.fade(outCubic(seg(t, c1, c1 + 0.3)), () => {
      K.words(L('effH'), MX, 330, { t, t0: c1 + 0.1, size: 36, weight: 700, fam: 'display', stagger: 0.02 })
      const eff: [string, string, boolean][] = [['e_p50', 'eval.latency_p50.p', false], ['e_p95', 'eval.latency_p95.p', false], ['e_costA', 'eval.cost_attempted', true], ['e_costR', 'eval.cost_resolved', true]]
      eff.forEach(([lbl, key, proj], i) => {
        const y = 440 + i * 110
        K.fade(outCubic(seg(t, c1 + 0.3 + i * 0.12, c1 + 0.7 + i * 0.12)), () => {
          K.text(L(lbl), MX, y, { size: 30, weight: 500 })
          K.label(L(proj ? 'projection' : 'measured'), MX, y + 32, { size: 22 })
          metricValue(K, M(key), 560, y + 8, { size: 40 })
        })
      })
    })
    field(K, 960, -4, 964, H + 8, C.blue, seg(t, c1 + 0.8, c1 + 1.4), 'right')
    K.fade(outCubic(seg(t, c1 + 1.2, c1 + 1.5)), () => {
      K.words(L('retH'), 1040, 330, { t, t0: c1 + 1.2, size: 40, weight: 700, fam: 'display', color: C.bg, stagger: 0.02 })
      K.text(L('r1'), 1040, 410, { size: 24, weight: 600, fam: 'mono', color: C.bg })
    })
    ;(['bm25', 'dense', 'hybrid'] as const).forEach((r, i) => {
      const m = M(`retrieval.r1.${r}`)
      const k = outExpo(seg(t, c1 + 1.4 + i * 0.15, c1 + 2.1 + i * 0.15))
      const y = 450 + i * 76
      K.fade(clamp(k * 3), () => {
        K.text(r, 1040, y + 32, { size: 26, weight: 600, fam: 'mono', color: C.bg })
        K.fillRR(1170, y + 6, 520 * m.num * k, 40, 6, C.bg)
        K.text(m.text, 1170 + 520 * m.num * k + 16, y + 36, { size: 30, weight: 800, fam: 'display', color: C.bg })
      })
    })
    K.fade(outCubic(seg(t, c1 + 2.2, c1 + 2.6)), () => {
      K.text(`${M('retrieval.abst_p.hybrid').text} / ${M('retrieval.abst_r.hybrid').text}`, 1040, 760, { size: 44, weight: 800, fam: 'display', color: C.bg })
      K.text(L('abst'), 1040, 800, { size: 24, weight: 600, fam: 'mono', color: C.bg })
      K.text(M('retrieval.p95.hybrid').text, 1520, 760, { size: 44, weight: 800, fam: 'display', color: C.bg })
      K.text(L('p95'), 1520, 800, { size: 24, weight: 600, fam: 'mono', color: C.bg })
      const r1 = M('retrieval.r1.hybrid')
      const cite = `${KIND_LABEL[r1.kind]}  |  ${r1.source}  |  ${M('retrieval.test_queries').text} ${L('retNote')}`
      K.wrap(cite, 800, 22, 500, 'mono').forEach((ln, i) => K.text(ln, 1040, H - 78 + i * 30, { size: 22, weight: 500, fam: 'mono', color: C.bg }))
      K.cite(`${KIND_LABEL.simulation} ${L('costCite')}`)
    })
  },
})
