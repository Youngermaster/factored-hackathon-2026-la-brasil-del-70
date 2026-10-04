/**
 * Click 3 of the hook (scenes/hook.ts): what the data really holds.
 *
 *   the pipeline   rows flow raw, bronze, silver, gold under contracts; one
 *                  bad row drops into quarantine instead of disappearing
 *   three findings each real data problem profiling found, and the design
 *                  decision it forced (a yellow tab: code decides)
 *
 * Numbers from data/metrics.yml; the findings are in docs/data/data-card.md
 * and docs/analysis/workflow-evidence.md.
 */
import type { SceneEnv } from '../../lib/scene/types'
import { C, MX } from '../../lib/scene/kit'
import { hash, outCubic, outExpo, presence, seg } from '../../lib/scene/math'
import { tab } from '../../lib/scene/bank'
import { packet, ring } from '../../lib/scene/fx'

const LANE = 330
const STAGES = ['s_raw', 's_bronze', 's_silver', 's_gold'] as const
const ROWS = [
  ['data.transcript_texts', 'f1', 'f1d'],
  ['data.orphan_branch_refs', 'f2', 'f2d'],
  ['data.complaint_foreign_product', 'f3', 'f3d'],
] as const

export function dataFindings({ t, L, M, K }: SceneEnv, t0: number, tout: number) {
  K.fade(presence(t, t0, tout, 0.3, 0.3), () => {
    // ── the pipeline: four stages, rows flowing, one dropped into quarantine
    const xs: number[] = []
    let x = MX
    STAGES.forEach((s, i) => {
      xs.push(x)
      x += K.chip(L(s), x, LANE - 26, { bg: C.bg2, fg: C.paper, size: 26, weight: 600, k: seg(t, t0 + 0.1 + i * 0.1, t0 + 0.5 + i * 0.1) }) + 40
      if (i < 3) K.arrow(x - 36, LANE, x - 8, LANE, { color: C.mute, lw: 2, head: 9, k: outCubic(seg(t, t0 + 0.3 + i * 0.1, t0 + 0.5 + i * 0.1)) })
    })
    const end = x - 40
    for (let j = 0; j < 6; j++) {
      const s = t0 + 0.5 + j * 0.12
      if (j === 2) packet(K, [{ x: MX, y: LANE + 30 }, { x: xs[2] + 30, y: LANE + 30 }, { x: xs[2] + 30, y: LANE + 84 }], seg(t, s, s + 0.7), C.red, 8)
      else packet(K, [{ x: MX, y: LANE + 30 }, { x: end, y: LANE + 30 }], seg(t, s, s + 0.9 + hash(j) * 0.2), C.paper, 7)
    }
    // where the bad row went stays drawn: a red drop line from silver into the quarantine tab
    const dk = outCubic(seg(t, t0 + 1.0, t0 + 1.3))
    if (dk > 0) K.line(xs[2] + 30, LANE + 24, xs[2] + 30, LANE + 24 + 66 * dk, C.red, 3)
    tab(K, L('quarantine'), xs[2], LANE + 92, { tone: 'red', k: seg(t, t0 + 1.1, t0 + 1.4), size: 22 })
    K.fade(outCubic(seg(t, t0 + 1.2, t0 + 1.6)), () => {
      K.text(M('data.rows_quarantined').text, end + 60, LANE + 14, { size: 48, weight: 800, fam: 'display' })
      K.label(L('quarantinedLbl'), end + 60, LANE + 54, { size: 22, color: C.dim })
      K.label(L('pipelineLbl'), end + 60, LANE + 90, { size: 22 })
    })

    // ── three findings, each with the decision it forced ─────────────────
    ROWS.forEach(([key, lbl, dec], r) => {
      const y = 620 + r * 125
      const s = t0 + 1.4 + r * 0.5
      const k = outExpo(seg(t, s, s + 0.6))
      if (k > 0) K.fillRR(MX - 30, y - 44, 8, 60 * k, 4, C.red)
      ring(K, MX - 26, y - 14, seg(t, s + 0.1, s + 0.7), C.red, 6, 44)
      K.fade(outCubic(seg(t, s, s + 0.4)), () => {
        K.text(M(key).text, MX, y + (1 - k) * 20, { size: 44, weight: 800, fam: 'display' })
        const sub = key === 'data.transcript_texts' ? `${L(lbl)} ${M('data.transcripts').text} ${L('f1b')}` : L(lbl)
        K.text(sub, 740, y - 2, { size: 26, weight: 500, color: C.dim })
      })
      K.arrow(1300, y - 12, 1340, y - 12, { color: C.yellow, lw: 3, head: 10, k: outCubic(seg(t, s + 0.4, s + 0.6)) })
      tab(K, L(dec), 1356, y - 32, { tone: 'yellow', k: seg(t, s + 0.5, s + 0.9), size: 22 })
    })
    K.fade(outCubic(seg(t, t0 + 0.4, t0 + 0.8)), () => K.cite(L('txCite')))
  })
}
