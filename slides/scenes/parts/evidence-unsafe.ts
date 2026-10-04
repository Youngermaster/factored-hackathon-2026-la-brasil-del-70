/**
 * The unsafe-outcome and weak-spot beats of the evidence scene
 * (scenes/evidence.ts).
 *
 *   3  three grids of the same 304 cases; the unsafe ones turn red one by
 *      one (P 8, B0 4, B1 90), then B1's red cases stream into what they did
 *   4  where P is weak: an instruction-like merchant name drops into the
 *      confirmation summary; a stolen-card message trips the model's distress
 *      flag and a transfer nobody needed
 */
import type { SceneEnv } from '../../lib/scene/types'
import { C, MX, type Kit } from '../../lib/scene/kit'
import { clamp, hash, lerp, outCubic, outExpo, presence, seg } from '../../lib/scene/math'
import { bubble, tab, tag } from '../../lib/scene/bank'
import { packet, ring } from '../../lib/scene/fx'
import { SYS } from './evidence-rates'

const COLS = 19
const ROWS = 16
const GAP = 18
export const GX = [MX, 560, 1000] as const
const GY = 340
/** the rank of every cell per system: the first `count` ranks are the unsafe cases */
const RANK = [0, 1, 2].map((s) => {
  const order = Array.from({ length: COLS * ROWS }, (_, i) => i).sort((a, b) => hash(a, s + 11) - hash(b, s + 11))
  const rank: number[] = []
  order.forEach((cell, r) => { rank[cell] = r })
  return rank
})
const cell = (s: number, i: number) => ({ x: GX[s] + 6 + (i % COLS) * GAP, y: GY + Math.floor(i / COLS) * GAP })

/** A grid of the 304 cases; k fills it in, `lit(rank)` is 0..1 for how red a cell is. */
export function grid(K: Kit, s: number, k: number, lit: (rank: number) => number) {
  if (k <= 0) return
  for (let i = 0; i < COLS * ROWS; i++) {
    const a = clamp(k * 1.6 - (i % COLS) / COLS * 0.6)
    if (a <= 0) continue
    const p = cell(s, i)
    const red = lit(RANK[s][i])
    K.fade(a, () => K.dot(p.x, p.y, red > 0 ? 6 + 2 * (1 - red) : 5, red > 0.5 ? C.red : C.mute))
  }
}

const B1_EVENTS = ['writes_unconfirmed', 'scores_disclosed', 'approval_wording', 'incomes_disclosed', 'wrong_figures'] as const

export function unsafe({ t, L, M, K }: SceneEnv, c3: number, c4: number) {
  K.fade(presence(t, c3 + 0.1, c4, 0.3, 0.25), () => {
    SYS.forEach((s, i) => {
      const m = M(`eval.unsafe.${s}`)
      const t0 = c3 + 1.0 + i * 0.2
      const span = i === 2 ? 1.4 : 0.6
      grid(K, i, seg(t, c3 + 0.2, c3 + 0.9), (r) => (r < m.num ? outCubic(seg(t, t0 + (r / m.num) * span, t0 + (r / m.num) * span + 0.2)) : 0))
      K.fade(outCubic(seg(t, t0 + span * 0.5, t0 + span * 0.5 + 0.4)), () => {
        K.text(m.text, GX[i], 700, { size: 48, weight: 800, fam: 'display' })
        K.label(`${m.lo} ${L('to')} ${m.hi}%`, GX[i], 742, { size: 22 })
      })
    })
    // B1's red cases stream into what they did
    const max = M('eval.b1.writes_unconfirmed').num
    B1_EVENTS.forEach((e, r) => {
      const m = M(`eval.b1.${e}`)
      const y = 350 + r * 84
      const t0 = c3 + 2.4 + r * 0.18
      for (let j = 0; j < 2; j++) {
        const src = cell(2, Math.floor(hash(r, j + 5) * COLS * ROWS))
        packet(K, [src, { x: 1430, y: y + 26 }], seg(t, t0 - 0.4 + j * 0.15, t0 + 0.2 + j * 0.15), C.red, 7)
      }
      K.fade(outCubic(seg(t, t0, t0 + 0.3)), () => K.text(L(e), 1430, y, { size: 24, weight: 500 }))
      const w = 300 * (m.num / max) * outExpo(seg(t, t0 + 0.1, t0 + 0.7))
      if (w > 0) K.fillRR(1430, y + 14, w, 22, 4, C.red)
      K.fade(outCubic(seg(t, t0 + 0.4, t0 + 0.7)), () => K.text(m.text, 1430 + w + 14, y + 34, { size: 28, weight: 800, fam: 'display', color: C.redText }))
    })
    K.fade(outCubic(seg(t, c3 + 3.4, c3 + 3.8)), () => {
      K.label(L('several'), 1430, 790, { size: 22 })
      K.label(`${M('eval.b1.credit_cases').text} ${L('inCredit')}`, 1430, 826, { size: 22, color: C.redText })
    })
  })
}

export function weak({ t, L, M, K }: SceneEnv, c4: number) {
  K.fade(outCubic(seg(t, c4 + 0.1, c4 + 0.4)), () => {
    // left: an instruction-like merchant name lands in the confirmation summary
    K.label(L('merchantLbl'), MX, 300, { size: 22 })
    const drop = outExpo(seg(t, c4 + 0.9, c4 + 1.5))
    const by = 470
    K.fade(outCubic(seg(t, c4 + 0.5, c4 + 0.9)), () => {
      K.label(L('summaryLbl'), MX, by - 16, { size: 22 })
      K.fillRR(MX, by, 760, 190, 18, C.bg2)
      K.strokeRR(MX, by, 760, 190, 18, C.faint, 2)
      K.fillRR(MX + 32, by + 40, 520, 12, 6, C.faint)
      K.fillRR(MX + 32, by + 140, 380, 12, 6, C.faint)
    })
    // where the chip came from stays as a dashed trace once it has dropped
    K.fade(outCubic(seg(t, c4 + 1.1, c4 + 1.5)) * 0.8, () => {
      K.ctx.save()
      K.ctx.setLineDash([8, 8])
      K.strokeRR(MX, 318, K.measure(L('merchant'), 22, 500, 'mono') + 32, 37, 10, C.mute, 2)
      K.ctx.restore()
    })
    const cy = lerp(318, by + 76, drop)
    K.chip(L('merchant'), MX + lerp(0, 32, drop), cy, { bg: C.redDeep, fg: C.redText, size: 22, k: seg(t, c4 + 0.3, c4 + 0.7), stroke: drop >= 1 ? C.red : undefined })
    ring(K, MX + 360, by + 95, seg(t, c4 + 1.5, c4 + 2.1), C.red, 10, 120)
    const real = M('eval.unsafe_real.p')
    K.fade(outCubic(seg(t, c4 + 1.9, c4 + 2.3)), () => {
      K.text(real.text, MX, 790, { size: 64, weight: 800, fam: 'display' })
      K.text(L('realLbl'), MX, 840, { size: 28, weight: 500 })
      K.text(L('realSub'), MX, 884, { size: 24, weight: 500, color: C.dim })
    })

    // right: a stolen card trips the distress flag, and a transfer nobody needed
    const RX = 1040
    bubble(K, L('stolen'), RX, 270, { k: seg(t, c4 + 0.6, c4 + 1.0), typed: seg(t, c4 + 0.7, c4 + 1.3), size: 30, maxW: 600, label: L('customer') })
    packet(K, [{ x: RX + 60, y: 380 }, { x: RX + 60, y: 482 }], seg(t, c4 + 1.3, c4 + 1.7), C.blue, 8)
    const w = tag(K, L('distress'), RX, 490, { tone: 'blue', k: seg(t, c4 + 1.6, c4 + 2.0), size: 24 })
    K.arrow(RX + w + 16, 512, RX + w + 70, 512, { color: C.red, k: outCubic(seg(t, c4 + 1.9, c4 + 2.2)), head: 12 })
    tab(K, L('transfer'), RX + w + 84, 490, { tone: 'red', k: seg(t, c4 + 2.1, c4 + 2.5), size: 24 })
    const card = M('eval.card_unnecessary.p')
    K.fade(outCubic(seg(t, c4 + 2.4, c4 + 2.8)), () => {
      K.text(card.text, RX, 790, { size: 64, weight: 800, fam: 'display' })
      K.text(L('cardLbl'), RX, 840, { size: 28, weight: 500 })
      K.text(`${L('cardSub')} ${L('sys0')} ${M('eval.sar.card_support.p').text}, ${L('sys1')} ${M('eval.sar.card_support.b0').text}`, RX, 884, { size: 24, weight: 500, color: C.dim })
    })
  })
}
