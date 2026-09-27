/**
 * Slide 1, the hook: the problem in the data.
 *
 *   arrive  23.5M rows counted in: the data is real work
 *   1 share one bar splits into what customers contact the bank for
 *   2 fcr   the same segments morph into first-contact resolution: disputes fail
 *   3 tx    147,292 transcripts collapse into two balance templates (honesty)
 *   4 scope four workflows, Spanish and Portuguese
 *
 * One bold move: the stacked bar morphing into columns (segment to column).
 */
import { defineScene } from '../lib/scene/types'
import { C, MX } from '../lib/scene/kit'
import { clamp, hash, inOutCubic, lerp, mix, outCubic, outExpo, presence, seg } from '../lib/scene/math'
import { source, tab } from '../lib/scene/bank'

const WF = ['account_inquiry', 'card_support', 'dispute', 'credit'] as const
const BX = MX
const BW = 1680
const BY = 480
const BH = 110

export default defineScene({
  cues: [3.0, 6.4, 9.8, 13.4, 16.6],
  draw({ t, L, M, K, ctx }) {
    // ── arrive: the counter ───────────────────────────────────────────────
    const aA = presence(t, 0, 3.05, 0.3, 0.25)
    K.fade(aA, () => {
      K.label(L('eyebrow'), MX, 300, { alpha: outCubic(seg(t, 0.1, 0.6)) })
      const rows = M('data.rows_ingested')
      K.text(K.count(0, rows.num, seg(t, 0.3, 2.3), ','), MX, 610, { size: 180, weight: 700, fam: 'display', ls: -0.03 })
      K.words(L('rows'), MX, 710, { t, t0: 1.2, size: 44, weight: 500, fam: 'sans', color: C.dim, ls: -0.01 })
      K.label(`${M('data.tables').text} ${L('rowsSub')}`, MX, 780, { alpha: outCubic(seg(t, 1.8, 2.3)) })
      source(K, rows, outCubic(seg(t, 1.8, 2.3)))
    })

    // ── 1 share, then 2 the morph into first-contact resolution ──────────
    const shares = [...WF, 'other'].map((w) => M(`share.${w}`))
    const total = shares.reduce((a, m) => a + m.num, 0)
    const m = inOutCubic(seg(t, 6.5, 7.6))
    const outBC = 1 - outCubic(seg(t, 9.85, 10.2))
    K.title(L('shareTitle'), t, 3.3, { tout: 6.45 })
    K.fade(presence(t, 3.4, 6.45) , () => {
      K.label(`${M('data.interactions').text} + ${M('data.complaints').text} ${L('shareSub')}  |  ${M('data.period').text}`, MX, 230)
    })
    let sx = BX
    shares.forEach((sh, i) => {
      const sw = (sh.num / total) * BW - 6
      const grow = outExpo(seg(t, 3.5 + i * 0.16, 4.2 + i * 0.16))
      const isOther = i === 4
      const fcr = isOther ? null : M(`fcr.${WF[i]}`)
      const colX = MX + i * 290
      const colH = fcr ? (fcr.num / 100) * 520 : 0
      const x = lerp(sx, colX, m)
      const w = lerp(sw * grow, 210, m)
      const h = lerp(BH, colH, m)
      const y = lerp(BY, 900 - colH, m)
      const isDispute = WF[i] === 'dispute'
      const col = isOther ? C.faint : isDispute ? mix(C.paper, C.red, m) : mix(C.paper, C.dim, m * 0.7)
      const a = (isOther ? 1 - clamp(m * 2) : 1) * outBC
      if (grow > 0 && a > 0) K.fade(a, () => K.fillRR(x, y, w, h, 4, col))
      // share labels under the stacked bar
      K.fade(clamp(grow * 2) * (1 - clamp(m * 3)) * outBC, () => {
        K.text(sh.text, sx, BY + BH + 64, { size: 36, weight: 700, fam: 'display', color: isOther ? C.mute : C.paper })
        K.label(L(isOther ? 'other' : WF[i]), sx, BY + BH + 104)
      })
      // first-contact-resolution labels on the columns
      if (fcr) {
        K.fade(presence(t, 7.4 + i * 0.08, 9.85), () => {
          K.text(fcr.text, colX, 900 - colH - 24, { size: 44, weight: 700, fam: 'display', color: isDispute ? C.red : C.paper })
          K.label(L(WF[i]), colX, 948, { color: isDispute ? C.redText : C.mute })
        })
      }
      sx += sw + 6
    })
    K.fade(presence(t, 3.6, 9.85), () => source(K, shares[0]))

    // the dispute panel, right of the columns
    K.title(L('fcrTitle'), t, 6.8, { tout: 9.85 })
    K.fade(outBC, () => {
      K.punch(L('fcrPunch'), t, 7.9, { x: 1320, y: 470, size: 48, maxW: 480, accent: C.red })
      const low = M('csat_low.dispute')
      const hd = M('handle.dispute')
      K.fade(outCubic(seg(t, 8.3, 8.8)), () => {
        K.text(low.text, 1320, 610, { size: 64, weight: 700, fam: 'display' })
        K.label(L('fcrLowCsat'), 1320, 656, { color: C.dim })
      })
      K.fade(outCubic(seg(t, 8.6, 9.1)), () => {
        K.text(hd.text, 1320, 780, { size: 64, weight: 700, fam: 'display' })
        K.label(L('fcrHandle'), 1320, 826, { color: C.dim })
      })
    })

    // ── 3 transcripts: 147,292 served, 42 texts, two balance questions ───
    const aD = presence(t, 10.0, 13.45, 0.3, 0.3)
    K.title(L('txTitle'), t, 10.1, { tout: 13.45 })
    K.fade(aD, () => {
      const stat = (v: string, lbl: string, y: number, t0: number) =>
        K.fade(outCubic(seg(t, t0, t0 + 0.4)), () => {
          K.text(v, MX, y + (1 - outExpo(seg(t, t0, t0 + 0.6))) * 30, { size: 96, weight: 700, fam: 'display' })
          K.label(lbl, MX, y + 48, { color: C.dim, size: 26 })
        })
      stat(M('data.transcripts').text, L('txServed'), 420, 10.3)
      stat(M('data.transcript_texts').text, L('txDistinct'), 600, 10.9)
      stat('2', L('txTwo'), 780, 11.8)
      // a wall of transcript lines that collapses into the two templates
      const col = inOutCubic(seg(t, 11.8, 12.6))
      for (let i = 0; i < 22; i++) {
        const w = 420 + hash(i, 3) * 560
        const y0 = 300 + i * 26
        const y1 = i % 2 ? 690 : 560
        const a = outCubic(seg(t, 10.3 + i * 0.025, 10.6 + i * 0.025)) * (1 - col) * 0.35
        if (a > 0) K.fade(a, () => K.fillRR(760, lerp(y0, y1, col) - 5, w, 10, 5, C.paper))
      }
      K.fade(outCubic(seg(t, 12.3, 12.8)), () => {
        K.text(L('txLine1'), 760, 570, { size: 30, weight: 500 })
        K.text(L('txLine2'), 760, 700, { size: 30, weight: 500 })
      })
      K.punch(L('txPunch'), t, 12.6, { y: 950, size: 40, accent: C.blueText })
      source(K, M('data.transcripts'), outCubic(seg(t, 10.4, 10.8)))
    })

    // ── 4 scope: four workflows, two languages ───────────────────────────
    const aE = outCubic(seg(t, 13.6, 13.9))
    K.title(L('scopeTitle'), t, 13.7)
    K.fade(aE, () => {
      WF.forEach((w, i) => {
        const k = outExpo(seg(t, 13.9 + i * 0.15, 14.6 + i * 0.15))
        K.fade(clamp(k * 2), () => {
          const y = 340 + i * 150 + (1 - k) * 30
          K.text(L(w), MX, y, { size: 48, weight: 700, fam: 'display' })
          K.text(L(`scope_${w}`), MX, y + 50, { size: 30, weight: 500, color: C.dim })
        })
      })
      const lk = seg(t, 14.8, 15.4)
      const w1 = tab(K, 'es', 1380, 300, { tone: 'paper', k: lk, size: 30 })
      tab(K, 'pt', 1380 + w1 + 16, 300, { tone: 'paper', k: seg(t, 14.9, 15.5), size: 30 })
      K.fade(outCubic(seg(t, 15.2, 15.7)), () => {
        K.text(L('langs'), 1380, 420, { size: 36, weight: 600 })
        K.wrap(L('langsNote'), 420, 26, 500).forEach((ln, i) => K.text(ln, 1380, 480 + i * 36, { size: 26, weight: 500, color: C.mute }))
      })
    })
    void ctx
  },
})
