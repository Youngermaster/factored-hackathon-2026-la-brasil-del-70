/**
 * Pitch slide 1 (static): the problem in the data, and who built the answer.
 *
 *   left    Bank Agent by La Brasil del 70; the synthetic bank (rows, tables,
 *           countries, contacts); disputes carry the pain (low satisfaction,
 *           handle time)
 *   right   first contact resolution by workflow, disputes lowest, each column
 *           with its share of contacts
 *   bottom  the team, names and roles as in the README
 */
import { defineScene } from '../lib/scene/types'
import { C, MX } from '../lib/scene/kit'
import { dims, source } from '../lib/scene/bank'
import { S, citeFit } from './parts/pitch-kit'

const WF = ['account_inquiry', 'card_support', 'dispute', 'credit'] as const

export default defineScene({
  cues: [30],
  draw({ L, M, K }) {
    const H = S.hook
    const CL = S.close
    dims(K, H('dims'))
    K.label(L('eyebrow'), MX, 72)

    // ── the product and the team name ─────────────────────────────────────
    K.text(CL('product'), MX, 196, { size: 88, weight: 800, fam: 'display', ls: -0.03 })
    K.text(L('tagline'), MX, 256, { size: 34, weight: 500, color: C.dim })

    // ── the synthetic bank ────────────────────────────────────────────────
    const rows = M('data.rows_ingested')
    K.text(rows.text, MX, 402, { size: 84, weight: 800, fam: 'display', ls: -0.03, color: C.paper })
    K.text(H('rows'), MX, 452, { size: 30, weight: 500, color: C.dim })
    K.label(`${M('data.tables').text} ${H('rowsSub')}`, MX, 494)
    K.label(`${M('data.interactions').text} + ${M('data.complaints').text} ${H('shareSub')}`, MX, 530)
    K.label(M('data.period').text, MX, 564)

    // ── disputes carry the pain ───────────────────────────────────────────
    K.fillRR(MX - 30, 610, 8, 226, 4, C.red)
    K.words(H('fcrPunch'), MX, 660, { t: 30, t0: 0, size: 46, weight: 600, fam: 'sans', ls: -0.01, accent: C.red })
    const low = M('csat_low.dispute')
    const hd = M('handle.dispute')
    K.text(low.text, MX, 760, { size: 60, weight: 700, fam: 'display' })
    K.label(H('fcrLowCsat'), MX, 806, { color: C.dim })
    K.text(hd.text, MX + 480, 760, { size: 60, weight: 700, fam: 'display' })
    K.label(H('fcrHandle'), MX + 480, 806, { color: C.dim })

    // ── first contact resolution by workflow ──────────────────────────────
    const X = 1010
    const BASE = 780
    K.text(H('fcrTitle'), X, 340, { size: 34, weight: 600 })
    K.label(L('fcrSub'), X, 378)
    WF.forEach((w, i) => {
      const fcr = M(`fcr.${w}`)
      const x = X + i * 200
      const h = (fcr.num / 100) * 330
      const red = w === 'dispute'
      K.fillRR(x, BASE - h, 160, h, 4, red ? C.red : C.dim)
      K.text(fcr.text, x, BASE - h - 18, { size: 38, weight: 700, fam: 'display', color: red ? C.red : C.paper })
      K.text(H(w), x, BASE + 40, { size: 26, weight: 600, color: red ? C.redText : C.paper })
      K.label(M(`share.${w}`).text, x, BASE + 74, { size: 22, color: C.mute })
    })

    // ── the team ──────────────────────────────────────────────────────────
    K.line(MX, 880, 1800, 880, C.faint, 2)
    K.label(`${CL('teamTitle')}  |  ${L('team')}`, MX, 918, { size: 22, color: C.yellow, weight: 600 })
    ;(['m1', 'm2', 'm3', 'm4'] as const).forEach((m, i) => {
      const x = MX + i * 420
      K.text(CL(m), x, 960, { size: 28, weight: 600 })
      K.label(CL(`${m}r`), x, 990, { size: 20, color: C.dim })
    })

    citeFit(K, `${L('cite')}`)
    void source
  },
})
