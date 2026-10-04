/**
 * The degradation ladder of the close scene (scenes/close.ts), phase 15:
 * failures hit, the service steps down L0 to L4, and at every level a write
 * is reported only after its read-back (L4 writes nothing at all).
 * Level names and triggers follow docs/operations/degradation.md.
 */
import type { SceneEnv } from '../../lib/scene/types'
import { C, MX } from '../../lib/scene/kit'
import { clamp, inOutCubic, lerp, outCubic, outExpo, presence, seg } from '../../lib/scene/math'
import { check, cross } from '../../lib/scene/bank'
import { ring } from '../../lib/scene/fx'

const N = 5
const SX = (i: number) => MX + i * 340
const SY = (i: number) => 360 + i * 96
const TW = 300
/** when the marker leaves level i for level i + 1 */
const HOP = (i: number) => 0.9 + i * 0.45

export function ladder({ t, L, K }: SceneEnv, tout: number) {
  K.fade(presence(t, 0.1, tout, 0.3, 0.25), () => {
    for (let i = 0; i < N; i++) {
      const k = seg(t, 0.2 + i * 0.08, 0.7 + i * 0.08)
      const x = SX(i)
      const y = SY(i)
      // the tread, its level tab, and what the level does
      if (k > 0) K.fillRR(x, y, TW * outExpo(k), 10, 5, i === 4 ? C.red : i === 0 ? C.yellow : C.dim)
      K.fade(outCubic(k), () => {
        K.chip(`L${i}`, x, y + 26, { bg: i === 4 ? C.red : C.bg2, fg: i === 4 ? C.bg : C.paper, size: 24, weight: 700 })
        K.text(L(`lv${i}`), x + 70, y + 54, { size: 26, weight: 500 })
      })
      // the failure that pushes the service down to this level
      if (i > 0) {
        const hit = HOP(i - 1)
        K.fade(outCubic(seg(t, hit - 0.2, hit)), () => K.label(L(`why${i}`), x, y + 96, { size: 22, color: C.redText }))
        ring(K, x + 20, y + 4, seg(t, hit + 0.15, hit + 0.6), C.red, 8, 60)
      }
      // the write lane: verified at L0 to L3, nothing written at L4
      const arrive = i ? HOP(i - 1) + 0.35 : 0.6
      const wk = seg(t, arrive, arrive + 0.3)
      if (i < 4) check(K, x + TW - 10, y - 30, 26, wk, C.yellow, 5)
      else cross(K, x + TW - 10, y - 30, 24, wk, C.red, 5)
    }
    // the service marker steps down one tread per failure
    let px = SX(0) + 150
    let py = SY(0)
    for (let i = 0; i < N - 1; i++) {
      const h = inOutCubic(seg(t, HOP(i), HOP(i) + 0.35))
      if (h <= 0) break
      px = lerp(SX(i) + 150, SX(i + 1) + 150, h)
      py = lerp(SY(i), SY(i + 1), h) - Math.sin(Math.PI * h) * 40
    }
    K.fade(outCubic(seg(t, 0.6, 0.9)), () => {
      K.dot(px, py - 18, 16, C.yellow)
      K.dot(px, py - 18, 7, C.bg)
    })
    K.punch(L('ladderPunch'), t, 2.7, { y: 930, size: 40, accent: C.yellow })
    void clamp
  })
}
