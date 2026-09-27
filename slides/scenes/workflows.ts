/**
 * Slide 4, the four workflows in depth.
 *
 *   arrive  the rail: four workflows with their share of contacts
 *   1..3    account inquiry, card support, dispute: three paths each
 *           (normal in yellow, ambiguous in blue, escalation in red)
 *   4       credit: the risk estimate kept apart from the synthetic
 *           eligibility decision, and no "approved" outcome
 *   5       the depth bar every workflow meets
 *
 * State names are the canonical ones in bank_agent.domain.workflow_catalog.
 */
import { defineScene } from '../lib/scene/types'
import { C, MX } from '../lib/scene/kit'
import { clamp, outCubic, outExpo, presence, seg } from '../lib/scene/math'
import { node, tag, type Tone } from '../lib/scene/bank'

const WF = ['account_inquiry', 'card_support', 'dispute', 'credit'] as const
const PRE = ['a', 'c', 'd'] as const
const CUES = [2.2, 5.0, 7.8, 10.6, 13.8, 16.4] as const
const SX = 640
const SW = 1160

export default defineScene({
  cues: CUES,
  draw({ t, L, M, K }) {
    K.title(L('title'), t, 0.1)
    K.fade(outCubic(seg(t, 1.2, 1.7)), () => K.cite(L('cite')))
    const active = t < CUES[0] + 0.1 ? -1 : t < CUES[4] + 0.1 ? Math.min(3, Math.floor(CUES.findIndex((c) => t < c + 0.1) - 1)) : 4

    // ── the rail ────────────────────────────────────────────────────────
    WF.forEach((w, i) => {
      const k = outExpo(seg(t, 0.4 + i * 0.12, 1.1 + i * 0.12))
      const on = active === i || active === 4
      const y = 330 + i * 130 + (1 - k) * 30
      K.fade(clamp(k * 2), () => {
        K.text(L(w), MX + 28, y, { size: 36, weight: 700, fam: 'display', color: on || active < 0 ? C.paper : C.mute })
        K.label(`${M(`share.${w}`).text} ${L('ofContacts')}`, MX + 28, y + 40, { size: 22 })
      })
      const bk = outCubic(seg(t, CUES[i] + 0.1, CUES[i] + 0.4)) * (1 - outCubic(seg(t, CUES[i + 1] + 0.05, CUES[i + 1] + 0.3)))
      if (bk > 0) K.fillRR(MX, y - 34, 6, 80 * bk, 3, C.yellow)
    })

    // ── one workflow's three paths ─────────────────────────────────────
    const paths = (p: string, tin: number, tout: number) => {
      K.fade(presence(t, tin, tout, 0.3, 0.25), () => {
        const rows: [string, Tone, string, string][] = [
          ['normal', 'yellow', L(`${p}_n`), L(`${p}_nNote`)],
          ['ambiguous', 'blue', L(`${p}_q`), L(`${p}_qNote`)],
          ['escalate', 'red', L(`${p}_e`), L(`${p}_eNote`)],
        ]
        rows.forEach(([lbl, tone, chips, note], r) => {
          const y = 320 + r * 200
          const t0 = tin + 0.2 + r * 0.5
          K.label(L(lbl), SX, y, { size: 22, alpha: outCubic(seg(t, t0, t0 + 0.3)) })
          let x = SX
          chips.split('|').forEach((c, j) => {
            const tj = t0 + 0.1 + j * 0.14
            if (j > 0) K.arrow(x - 34, y + 38, x - 10, y + 38, { color: C.mute, lw: 2, head: 9, k: outCubic(seg(t, tj - 0.05, tj + 0.1)) })
            x += tag(K, c, x, y + 18, { tone, k: seg(t, tj, tj + 0.4), size: 22 }) + 44
          })
          K.fade(outCubic(seg(t, t0 + 0.4, t0 + 0.8)), () =>
            K.wrap(note, SW, 26, 500).forEach((ln, i) => K.text(ln, SX, y + 104 + i * 34, { size: 26, weight: 500, color: C.dim })))
        })
      })
    }
    PRE.forEach((p, i) => paths(p, CUES[i] + 0.1, CUES[i + 1] + 0.05))

    // ── credit: separation of risk and eligibility ─────────────────────
    const c0 = CUES[3] + 0.1
    K.fade(presence(t, c0, CUES[4] + 0.05, 0.3, 0.25), () => {
      node(K, SX, 300, 260, 100, { label: L('k_llm'), sub: L('k_llmSub'), tone: 'blue', k: seg(t, c0 + 0.1, c0 + 0.6), size: 28 })
      const wk = outCubic(seg(t, c0 + 0.5, c0 + 0.9))
      if (wk > 0) {
        K.line(SX + 300, 350 - 70 * wk, SX + 300, 350 + 70 * wk, C.red, 5)
        K.fade(outCubic(seg(t, c0 + 0.8, c0 + 1.1)), () =>
          K.wrap(L('k_wall'), 260, 22, 500, 'mono').forEach((ln, i) => K.label(ln, SX, 450 + i * 30, { size: 22, color: C.redText })))
      }
      node(K, SX + 340, 300, 380, 100, { label: L('k_risk'), sub: L('k_riskSub'), tone: 'paper', k: seg(t, c0 + 0.9, c0 + 1.4), size: 28 })
      K.arrow(SX + 730, 350, SX + 776, 350, { color: C.mute, k: outCubic(seg(t, c0 + 1.3, c0 + 1.5)) })
      node(K, SX + 790, 300, 330, 100, { label: L('k_elg'), sub: L('k_elgSub'), tone: 'yellow', k: seg(t, c0 + 1.4, c0 + 1.9), size: 28 })
      const outs: [string, Tone][] = [['k_o1', 'yellow'], ['k_o2', 'yellow'], ['k_o3', 'red'], ['k_o4', 'blue']]
      let x = SX + 340
      outs.forEach(([key, tone], i) => {
        const w = tag(K, L(key), x, 560 + (i % 2) * 62, { tone, k: seg(t, c0 + 1.9 + i * 0.12, c0 + 2.3 + i * 0.12), size: 22 })
        if (i % 2 === 1) x += Math.max(w, 300) + 24
      })
      K.fade(outCubic(seg(t, c0 + 2.4, c0 + 2.7)), () => {
        const w = K.chip(L('k_approved'), SX + 340, 720, { bg: C.bg2, fg: C.mute, size: 22 })
        K.line(SX + 334, 740, SX + 346 + w * outCubic(seg(t, c0 + 2.5, c0 + 2.8)), 740, C.red, 3)
        K.wrap(L('k_note'), 700, 26, 500).forEach((ln, i) => K.text(ln, SX + 340, 820 + i * 34, { size: 26, weight: 500, color: C.dim }))
      })
    })

    // ── the depth bar ───────────────────────────────────────────────────
    const s0 = CUES[4] + 0.1
    K.fade(outCubic(seg(t, s0, s0 + 0.3)), () => {
      K.words(L('bar_h'), SX, 330, { t, t0: s0 + 0.1, size: 40, weight: 700, fam: 'display', stagger: 0.03 })
      for (let i = 0; i < 6; i++) {
        const k = outExpo(seg(t, s0 + 0.4 + i * 0.1, s0 + 1.0 + i * 0.1))
        const y = 430 + i * 72 + (1 - k) * 20
        K.fade(clamp(k * 2), () => {
          K.fillRR(SX, y - 18, 16, 4, 2, C.yellow)
          K.text(L(`bar${i + 1}`), SX + 36, y - 6, { size: 32, weight: 500, base: 'middle' })
        })
      }
    })
  },
})
