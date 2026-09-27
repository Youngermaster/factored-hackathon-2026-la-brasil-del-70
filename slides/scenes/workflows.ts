/**
 * Slide 4, the four workflows in depth.
 *
 *   arrive  four filled tiles: the workflows and their share of contacts
 *   1..3    account inquiry, card support, dispute: three filled paths each
 *           (normal yellow, ambiguous blue, escalation red); a packet walks
 *           the normal path state by state
 *   4       credit: the estimate flows to the synthetic eligibility policy and
 *           bounces off the wall in front of the language model
 *   5       the tiles fly up into column headers and the same six depth
 *           checkpoints light up under every workflow
 *
 * State names are the canonical ones in bank_agent.domain.workflow_catalog.
 */
import { defineScene } from '../lib/scene/types'
import { C, MX } from '../lib/scene/kit'
import { clamp, inOutCubic, lerp, outCubic, presence, seg } from '../lib/scene/math'
import { tab, type Tone } from '../lib/scene/bank'
import { packet } from '../lib/scene/fx'
import { credit, depthGrid } from './parts/workflows-extra'

const WF = ['account_inquiry', 'card_support', 'dispute', 'credit'] as const
const PRE = ['a', 'c', 'd'] as const
const CUES = [2.2, 5.0, 7.8, 10.6, 13.8, 16.4] as const
const SX = 640

export default defineScene({
  cues: CUES,
  draw(env) {
    const { t, L, M, K } = env
    K.title(L('title'), t, 0.1, { tout: CUES[4] + 0.05 })
    K.fade(outCubic(seg(t, 1.2, 1.7)), () => K.cite(L('cite')))
    const active = t < CUES[0] + 0.1 ? -1 : Math.min(3, CUES.findIndex((c) => t < c + 0.1) - 1)
    const g = inOutCubic(seg(t, CUES[4] + 0.1, CUES[4] + 0.9))

    // ── the tiles: a rail on the left, then column headers of the grid ───
    WF.forEach((w, i) => {
      const k = outCubic(seg(t, 0.3 + i * 0.12, 0.9 + i * 0.12))
      if (k <= 0) return
      const on = active === i || g > 0
      const x = lerp(MX, 640 + i * 290, g)
      const y = lerp(270 + i * 140, 250, g) + (1 - k) * 30
      const w0 = lerp(420, 260, g)
      const h0 = lerp(116, 96, g)
      K.fade(k, () => {
        K.fillRR(x, y, w0, h0, 12, on ? C.paper : C.bg2)
        const size = 28
        const lines = K.wrap(L(w), w0 - 48, size, 700, 'display')
        lines.forEach((ln, j) => K.text(ln, x + 24, y + 44 + j * 34, { size, weight: 700, fam: 'display', color: on ? C.bg : C.dim }))
        K.fade(1 - g, () => K.label(`${M(`share.${w}`).text} ${L('ofContacts')}`, x + 24, y + h0 - 22, { size: 22, color: on ? C.inkMute : C.mute }))
      })
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
          const y = 300 + r * 200
          const t0 = tin + 0.2 + r * 0.5
          K.label(L(lbl), SX, y, { size: 22, alpha: outCubic(seg(t, t0, t0 + 0.3)) })
          let x = SX
          const centers: { x: number; y: number }[] = []
          chips.split('|').forEach((c, j) => {
            const tj = t0 + 0.1 + j * 0.14
            if (j > 0) K.arrow(x - 34, y + 40, x - 10, y + 40, { color: C.mute, lw: 2, head: 9, k: outCubic(seg(t, tj - 0.05, tj + 0.1)) })
            const w = tab(K, c, x, y + 18, { tone, k: seg(t, tj, tj + 0.4), size: 24 })
            centers.push({ x: x + w / 2, y: y + 76 })
            x += w + 44
          })
          // a packet walks the normal path, state by state
          if (r === 0 && centers.length > 1) packet(K, centers, seg(t, tin + 1.2, tin + 2.2), C.yellow, 7)
          K.fade(outCubic(seg(t, t0 + 0.4, t0 + 0.8)), () => K.text(note, SX, y + 124, { size: 28, weight: 500, color: C.dim }))
        })
      })
    }
    PRE.forEach((p, i) => paths(p, CUES[i] + 0.1, CUES[i + 1] + 0.05))

    credit(env, CUES[3] + 0.1, CUES[4] + 0.05)
    depthGrid(env, CUES[4] + 0.1)
    void clamp
  },
})
