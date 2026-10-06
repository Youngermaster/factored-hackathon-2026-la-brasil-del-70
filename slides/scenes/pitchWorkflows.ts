/**
 * Pitch slide 4 (static): the four workflows, each built to the same depth.
 *
 *   top     one card per workflow with its share of contacts and its three
 *           paths (normal yellow, ambiguous blue, escalation red)
 *   middle  credit: the risk estimate goes to the synthetic eligibility
 *           policy, never to the language model; no approved outcome exists
 *   bottom  the depth bar every workflow meets
 *
 * Wording from the video deck's workflows scene (locales/en.yml); facts in
 * docs/architecture/workflow-registry.md and credit-separation.md.
 */
import { defineScene } from '../lib/scene/types'
import { C, MX } from '../lib/scene/kit'
import { dims, node, tab } from '../lib/scene/bank'
import { S, citeFit, ptitle } from './parts/pitch-kit'

const WF = ['account_inquiry', 'card_support', 'dispute', 'credit'] as const
const CW = 390
const GAP = (1680 - 4 * CW) / 3
const PATHS = [['normal', C.yellow, C.yellow], ['ambiguous', C.blue, C.blueText], ['escalate', C.red, C.redText]] as const

export default defineScene({
  cues: [30],
  draw({ L, M, K }) {
    const WK = S.workflows
    dims(K, WK('dims'))
    ptitle(K, WK('title'))

    // ── the four cards ────────────────────────────────────────────────────
    const notes: Record<string, readonly string[]> = {
      account_inquiry: [WK('a_nNote'), WK('a_qNote'), WK('a_eNote')],
      card_support: [WK('c_nNote'), WK('c_qNote'), WK('c_eNote')],
      dispute: [WK('d_nNote'), WK('d_qNote'), WK('d_eNote')],
      credit: [L('k_n'), L('k_q'), L('k_e')],
    }
    WF.forEach((w, i) => {
      const x = MX + i * (CW + GAP)
      K.fillRR(x, 206, CW, 432, 12, C.bg2)
      K.fillRR(x, 206, CW, 8, 4, w === 'dispute' ? C.red : C.paper)
      K.text(WK(w), x + 24, 256, { size: 30, weight: 700, fam: 'display' })
      K.label(`${M(`share.${w}`).text} ${WK('ofContacts')}`, x + 24, 290, { size: 22, color: C.dim })
      let y = 308
      PATHS.forEach(([p, bg, fg], j) => {
        K.chip(WK(p), x + 24, y, { bg, fg: C.bg, size: 20, weight: 700 })
        const lines = K.wrap(notes[w][j], CW - 48, 22, 500, 'sans')
        lines.forEach((ln, k) => K.text(ln, x + 24, y + 60 + k * 28, { size: 22, weight: 500, color: C.paper }))
        y += 34 + 4 + lines.length * 28 + 14
        void fg
      })
    })

    // ── credit: risk and eligibility apart from the model ─────────────────
    K.label(L('creditH'), MX, 690, { size: 22, color: C.dim })
    node(K, MX, 708, 300, 96, { label: WK('k_llm'), sub: WK('k_llmSub'), tone: 'blue', filled: true, size: 28 })
    K.fillRR(452, 700, 10, 112, 5, C.red)
    K.label(WK('k_wall'), MX, 842, { size: 20, color: C.redText })
    node(K, 500, 708, 300, 96, { label: WK('k_risk'), sub: WK('k_riskSub'), tone: 'paper', filled: true, size: 28 })
    K.arrow(808, 756, 846, 756, { color: C.dim, lw: 3, head: 10 })
    node(K, 854, 708, 300, 96, { label: WK('k_elg'), sub: WK('k_elgSub'), tone: 'yellow', filled: true, size: 28 })
    K.arrow(1162, 756, 1200, 756, { color: C.dim, lw: 3, head: 10 })
    tab(K, WK('k_o1'), 1210, 704, { tone: 'yellow', size: 22 })
    tab(K, WK('k_o2'), 1540, 704, { tone: 'yellow', size: 22 })
    tab(K, WK('k_o3'), 1210, 756, { tone: 'red', size: 22 })
    tab(K, WK('k_o4'), 1540, 756, { tone: 'blue', size: 22 })
    const aw = K.chip(WK('k_approved'), 1210, 812, { bg: C.bg2, fg: C.mute, size: 22 })
    K.line(1204, 831, 1216 + aw, 831, C.red, 3)
    K.text(WK('k_note'), 1210 + aw + 24, 838, { size: 24, weight: 500, color: C.dim })

    // ── the depth bar ─────────────────────────────────────────────────────
    K.line(MX, 884, 1800, 884, C.faint, 2)
    K.text(WK('bar_h'), MX, 940, { size: 30, weight: 700, fam: 'display' })
    let bx = 760
    ;(['bar1', 'bar2', 'bar3', 'bar4', 'bar5', 'bar6'] as const).forEach((b) => {
      bx += tab(K, WK(b), bx, 910, { tone: 'yellow', size: 22 }) + 14
    })
    citeFit(K, WK('cite'))
  },
})
