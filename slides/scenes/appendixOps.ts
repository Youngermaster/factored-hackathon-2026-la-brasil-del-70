/**
 * Appendix: operations (phase 15), for questions.
 *
 *   arrive  one turn as a trace: the spans draw in as the turn runs (model
 *           calls blue, decisions and tools yellow), and the same trace id
 *           threads the response header, the logs and the execution record
 *   1       the budget guard: every model call reserves its worst case in a
 *           shared ledger; an alert first, then the cap drops the service to
 *           L2 (templates only). Beside it, the local load test on the
 *           production stack, labeled a simulation
 *
 * Span names follow docs/operations/observability.md; the timing is drawn,
 * not measured.
 */
import { defineScene } from '../lib/scene/types'
import { C, MX } from '../lib/scene/kit'
import { clamp, outCubic, outExpo, presence, seg } from '../lib/scene/math'
import { source, tab } from '../lib/scene/bank'
import { packet } from '../lib/scene/fx'

const CUES = [3.4, 6.8] as const
const X0 = 760
const X1 = 1760
/** span: name key, colour, start and end as a share of the turn, depth */
const SPANS = [
  ['s0', C.dim, 0, 1, 0], ['s1', C.paper, 0.02, 0.98, 1], ['s2', C.blue, 0.04, 0.14, 2], ['s3', C.yellow, 0.15, 0.96, 2],
  ['s4', C.yellow, 0.17, 0.25, 3], ['s5', C.blue, 0.27, 0.71, 3], ['s6', C.yellow, 0.73, 0.9, 3], ['s7', C.dim, 0.77, 0.86, 4],
] as const

export default defineScene({
  cues: CUES,
  draw({ t, L, M, K }) {
    K.label(L('eyebrow'), MX, 66, { size: 22, alpha: outCubic(seg(t, 0.1, 0.4)) })
    const c1 = CUES[0] + 0.05

    // ── arrive: one turn as a trace ───────────────────────────────────────
    K.title(L('t0'), t, 0.1, { tout: c1 })
    K.fade(presence(t, 0.2, c1, 0.3, 0.25), () => {
      SPANS.forEach(([key, color, a, b, depth], i) => {
        const y = 300 + i * 60
        const t0 = 0.4 + a * 1.6
        const k = seg(t, t0, t0 + Math.max(0.25, (b - a) * 1.6))
        K.fade(outCubic(seg(t, t0 - 0.1, t0 + 0.2)), () => K.text(L(key), MX + depth * 24, y + 8, { size: 24, weight: 500, fam: 'mono', color: color === C.blue ? C.blueText : color === C.dim ? C.dim : color }))
        if (k > 0) K.fillRR(X0 + (X1 - X0) * a, y - 14, Math.max(8, (X1 - X0) * (b - a) * k), 28, 5, color)
      })
      // one trace id threads the header, the logs and the record
      const y = 850
      const items = ['h0', 'h1', 'h2'] as const
      let x = MX
      const xs: number[] = []
      items.forEach((key, i) => {
        xs.push(x)
        x += tab(K, L(key), x, y, { tone: 'yellow', k: seg(t, 2.2 + i * 0.15, 2.6 + i * 0.15), size: 24 }) + 80
      })
      for (let i = 0; i < 2; i++) K.arrow(xs[i + 1] - 72, y + 20, xs[i + 1] - 10, y + 20, { color: C.yellow, k: outCubic(seg(t, 2.5 + i * 0.15, 2.8 + i * 0.15)), head: 10 })
      K.fade(outCubic(seg(t, 2.7, 3.0)), () => K.label(L('traceNote'), MX, 940, { size: 22 }))
      K.cite(L('citeTrace'), outCubic(seg(t, 1.6, 2.0)))
    })

    // ── 1 the budget guard, and capacity ──────────────────────────────────
    K.title(L('t1'), t, c1 + 0.1)
    K.fade(outCubic(seg(t, c1, c1 + 0.3)), () => {
      const BX = MX
      const BW = 760
      const BY = 400
      K.label(L('budgetLbl'), BX, BY - 24, { size: 24, color: C.dim })
      K.strokeRR(BX, BY, BW, 64, 10, C.faint, 3)
      // calls reserve their worst case one block at a time
      const n = 10
      for (let i = 0; i < n; i++) {
        const t0 = c1 + 0.5 + i * 0.16
        packet(K, [{ x: BX + 40 + i * 74, y: BY - 90 }, { x: BX + 40 + i * 74, y: BY + 32 }], seg(t, t0 - 0.3, t0), C.blue, 7)
        const k = outExpo(seg(t, t0, t0 + 0.25))
        if (k > 0) K.fillRR(BX + 6 + i * 74.8, BY + 6, 70 * k, 52, 6, i === n - 1 ? C.red : C.blue)
      }
      // the alert line, then the cap
      const ak = outCubic(seg(t, c1 + 1.7, c1 + 2.0))
      if (ak > 0) K.line(BX + BW * 0.8, BY - 20, BX + BW * 0.8, BY + 84 * ak, C.yellow, 4)
      K.fade(ak, () => K.label(L('alert'), BX + BW * 0.8 - 10, BY + 110, { size: 22, color: C.yellow, align: 'right' }))
      K.arrow(BX + BW + 16, BY + 32, BX + BW + 90, BY + 32, { color: C.red, k: outCubic(seg(t, c1 + 2.3, c1 + 2.6)), head: 12 })
      K.fade(outCubic(seg(t, c1 + 2.5, c1 + 2.8)), () => {
        K.chip(L('l2'), BX + BW + 100, BY + 12, { bg: C.red, fg: C.bg, size: 24, weight: 700 })
        K.text(L('reserve'), BX, BY + 170, { size: 28, weight: 500 })
        K.text(L('reserveSub'), BX, BY + 210, { size: 24, weight: 500, color: C.dim })
      })
      // capacity on the right
      const RX = 1260
      const k = outExpo(seg(t, c1 + 0.8, c1 + 1.5))
      K.fade(clamp(k * 2), () => {
        K.text(M('ops.load_tps').text, RX, 620 + (1 - k) * 24, { size: 120, weight: 800, fam: 'display' })
        K.text(L('tps'), RX, 680, { size: 30, weight: 500 })
        K.text(`${M('ops.load_users').text} ${L('users')}  |  p95 ${M('ops.load_p95').text}`, RX, 724, { size: 24, weight: 500, color: C.dim })
        K.label(L('loadNote'), RX, 768, { size: 22 })
      })
      source(K, M('ops.load_tps'), outCubic(seg(t, c1 + 1.0, c1 + 1.4)), L('citeBudget'))
    })
  },
})
