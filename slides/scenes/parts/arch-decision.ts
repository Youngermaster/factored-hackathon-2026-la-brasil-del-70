/**
 * Click 3 of the architecture scene: the model decision.
 *
 *   rows 1 to 3  each learned component against its served baseline, on its
 *                own held-out test split: the learned bar grows past the
 *                baseline (router macro-F1, resolver coverage, risk ROC AUC)
 *   row 4        P end to end on the dev split: the two intervals overlap
 *   the decision the baselines stay the default; the learned models stay
 *                one setting away
 *
 * Numbers from data/metrics.yml (ml.*); sources docs/models and
 * docs/evaluation/results.md ("Decision: the learned router...").
 */
import type { SceneEnv } from '../../lib/scene/types'
import { C, MX } from '../../lib/scene/kit'
import { clamp, outCubic, outExpo, seg } from '../../lib/scene/math'
import { tab } from '../../lib/scene/bank'

const X0 = 820
const X1 = 1500
const ROWS = [
  ['d_rtr', 'ml.router.f1.keyword', 'ml.router.f1.embeddings', 'd_rtrB', 'd_rtrL'],
  ['d_res', 'ml.resolver.coverage.rules', 'ml.resolver.coverage.lgbm', 'd_resB', 'd_resL'],
  ['d_risk', 'ml.risk.auc.score_band', 'ml.risk.auc.logreg', 'd_riskB', 'd_riskL'],
] as const
/** the end-to-end row's scale: safe automated resolution from 50% to 80% */
const ex = (v: number) => X0 + ((X1 - X0) * (v - 50)) / 30

export function decision({ t, L, M, K }: SceneEnv, c3: number) {
  K.fade(outCubic(seg(t, c3, c3 + 0.3)), () => {
    // legend: baseline in ink grey, learned in blue (a model)
    K.fade(outCubic(seg(t, c3 + 0.2, c3 + 0.5)), () => {
      K.fillRR(X0, 262, 28, 14, 4, C.inkMute)
      K.label(L('d_base'), X0 + 40, 276, { size: 22, color: C.inkDim })
      K.fillRR(X0 + 300, 262, 28, 14, 4, C.blue)
      K.label(L('d_learned'), X0 + 340, 276, { size: 22, color: C.inkDim })
    })
    ROWS.forEach(([lbl, base, learned, bl, ll], r) => {
      const y = 360 + r * 140
      const s = c3 + 0.3 + r * 0.3
      K.fade(outCubic(seg(t, s, s + 0.3)), () => {
        K.text(L(lbl), MX, y + 6, { size: 30, weight: 700, color: C.bg })
        K.label(L(`${lbl}M`), MX, y + 42, { size: 22, color: C.inkDim })
      })
      const bars: [string, string, string, number][] = [[base, bl, C.inkMute, 0], [learned, ll, C.blue, 1]]
      for (const [key, name, fill, i] of bars) {
        const m = M(key)
        const k = outExpo(seg(t, s + 0.15 + i * 0.25, s + 0.75 + i * 0.25))
        const by = y - 22 + i * 40
        if (k > 0) K.fillRR(X0, by, Math.max(8, (X1 - X0) * m.num * k), 24, 5, fill)
        K.fade(clamp(k * 2 - 1), () => {
          const vx = X0 + (X1 - X0) * m.num + 16
          K.text(m.text, vx, by + 21, { size: 26, weight: 700, fam: 'mono', color: C.bg })
          K.label(L(name), vx + 84, by + 20, { size: 22, color: C.inkDim })
        })
      }
    })

    // the end-to-end row: two overlapping intervals on the dev split
    const y = 790
    const s = c3 + 1.5
    K.fade(outCubic(seg(t, s, s + 0.3)), () => {
      K.text(L('d_e2e'), MX, y + 6, { size: 30, weight: 700, color: C.bg })
      K.label(L('d_e2eM'), MX, y + 42, { size: 22, color: C.inkDim })
    })
    ;([['ml.e2e.dev.baselines', C.inkMute], ['ml.e2e.dev.learned', C.blue]] as const).forEach(([key, fill], i) => {
      const m = M(key)
      const k = outExpo(seg(t, s + 0.2 + i * 0.2, s + 0.8 + i * 0.2))
      const by = y - 14 + i * 34
      const c = ex(m.num)
      if (k > 0) K.fillRR(c - (c - ex(m.lo)) * k, by, Math.max(10, (ex(m.hi) - ex(m.lo)) * k), 12, 6, fill)
      K.fade(clamp(k * 2 - 1), () => {
        K.dot(c, by + 6, 10, fill)
        K.text(m.text, ex(m.hi) + 16, by + 14, { size: 24, weight: 700, fam: 'mono', color: C.bg })
      })
    })
    tab(K, L('d_verdict'), X0, 880, { tone: 'yellow', k: seg(t, s + 1.0, s + 1.4), size: 24 })
    K.fade(outCubic(seg(t, s + 1.2, s + 1.6)), () => K.label(L('d_verdictS'), X0, 960, { size: 22, color: C.inkDim }))
    K.fade(outCubic(seg(t, c3 + 0.6, c3 + 1.0)), () => K.cite(L('cite3'), 1, C.inkMute))
  })
}
