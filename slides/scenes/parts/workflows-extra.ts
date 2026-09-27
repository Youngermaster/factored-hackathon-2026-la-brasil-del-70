/**
 * The credit separation beat and the depth grid of the workflows scene
 * (scenes/workflows.ts), split out to keep each file readable.
 */
import type { SceneEnv } from '../../lib/scene/types'
import { C, MX } from '../../lib/scene/kit'
import { clamp, outCubic, outExpo, presence, seg } from '../../lib/scene/math'
import { node, tab, type Tone } from '../../lib/scene/bank'
import { glyph, packet, ring, type GlyphKind } from '../../lib/scene/fx'

const SX = 640

/** Credit: the risk estimate feeds the synthetic eligibility policy, never the model. */
export function credit({ t, L, K }: SceneEnv, c0: number, tout: number) {
  K.fade(presence(t, c0, tout, 0.3, 0.25), () => {
    node(K, SX, 300, 260, 100, { label: L('k_llm'), sub: L('k_llmSub'), tone: 'blue', k: seg(t, c0 + 0.1, c0 + 0.6), size: 28, filled: true })
    const wk = outExpo(seg(t, c0 + 0.5, c0 + 0.9))
    if (wk > 0) K.fillRR(SX + 290, 350 - 90 * wk, 14, 180 * wk, 7, C.red)
    K.fade(outCubic(seg(t, c0 + 0.8, c0 + 1.1)), () =>
      K.wrap(L('k_wall'), 250, 22, 500, 'mono').forEach((ln, i) => K.label(ln, SX, 470 + i * 30, { size: 22, color: C.redText })))
    node(K, SX + 340, 300, 380, 100, { label: L('k_risk'), sub: L('k_riskSub'), tone: 'paper', k: seg(t, c0 + 0.9, c0 + 1.4), size: 28, filled: true })
    node(K, SX + 790, 300, 330, 100, { label: L('k_elg'), sub: L('k_elgSub'), tone: 'yellow', k: seg(t, c0 + 1.3, c0 + 1.8), size: 28, filled: true })
    // the estimate: one copy flows on to eligibility, one bounces off the wall
    packet(K, [{ x: SX + 720, y: 350 }, { x: SX + 790, y: 350 }], seg(t, c0 + 1.8, c0 + 2.2), C.paper, 9)
    if (t > c0 + 1.8 && t < c0 + 2.6) {
      const go = outCubic(seg(t, c0 + 1.8, c0 + 2.1))
      const back = outCubic(seg(t, c0 + 2.1, c0 + 2.5))
      const x = SX + 330 - 20 * go + 50 * back
      K.fade(1 - seg(t, c0 + 2.2, c0 + 2.6), () => K.dot(x, 350, 10, C.paper))
    }
    ring(K, SX + 310, 350, seg(t, c0 + 2.1, c0 + 2.6), C.red, 10, 80)
    const outs: [string, Tone][] = [['k_o1', 'yellow'], ['k_o2', 'yellow'], ['k_o3', 'red'], ['k_o4', 'blue']]
    let x = SX + 340
    outs.forEach(([key, tone], i) => {
      const w = tab(K, L(key), x, 560 + (i % 2) * 64, { tone, k: seg(t, c0 + 2.2 + i * 0.1, c0 + 2.6 + i * 0.1), size: 24 })
      if (i % 2 === 1) x += Math.max(w, 330) + 24
    })
    K.fade(outCubic(seg(t, c0 + 2.6, c0 + 2.9)), () => {
      const w = K.chip(L('k_approved'), SX + 340, 740, { bg: C.bg2, fg: C.mute, size: 24 })
      K.line(SX + 334, 761, SX + 346 + w * outCubic(seg(t, c0 + 2.7, c0 + 3.0)), 761, C.red, 4)
      K.text(L('k_note'), SX + 340, 860, { size: 28, weight: 500, color: C.dim })
    })
  })
}

const ROWS: readonly [GlyphKind, string][] = [
  ['clause', C.yellow], ['states', C.yellow], ['verified', C.yellow], ['handoff', C.red], ['lang', C.blue], ['eval', C.paper],
]

/** The same six checkpoints light up under every workflow, in a diagonal wave. */
export function depthGrid({ t, L, K }: SceneEnv, s0: number) {
  K.words(L('bar_h'), MX, 150, { t, t0: s0 + 0.2, size: 56, weight: 700, fam: 'display' })
  ROWS.forEach(([kind, color], r) => {
    const y = 430 + r * 86
    const k = outCubic(seg(t, s0 + 0.5 + r * 0.06, s0 + 0.9 + r * 0.06))
    glyph(K, kind, MX + 24, y, 34, color, k)
    K.fade(k, () => K.text(L(`bar${r + 1}`), MX + 70, y + 9, { size: 26, weight: 500, fam: 'mono', color: C.paper }))
    for (let c = 0; c < 4; c++) {
      const cx = 640 + c * 290 + 130
      const ck = seg(t, s0 + 0.9 + (r + c) * 0.07, s0 + 1.3 + (r + c) * 0.07)
      if (ck <= 0) continue
      const e = outExpo(ck)
      K.fade(clamp(ck * 3), () => {
        K.fillRR(cx - 75 * e, y - 30, 150 * e, 60, 10, color)
        glyph(K, kind, cx, y, 30, C.bg, ck)
      })
    }
  })
}
