/**
 * Slide 1, the hook: the problem in the data.
 *
 *   arrive  23.5M rows counted in: the data is real work
 *   1 share one bar splits into what customers contact the bank for
 *   2 fcr   the same segments morph into first contact resolution: disputes fail
 *   3 data  the pipeline (raw to gold, bad rows quarantined) and three real
 *           data problems, each with the decision it forced (scenes/parts/hook-data.ts)
 *   4 scope four workflows, Spanish and Portuguese
 *
 * One bold move: the stacked bar morphing into columns (segment to column).
 */
import { defineScene } from '../lib/scene/types'
import { C, H, MX, W } from '../lib/scene/kit'
import { clamp, inOutCubic, lerp, mix, outCubic, outExpo, presence, seg } from '../lib/scene/math'
import { dims, source } from '../lib/scene/bank'
import { field } from '../lib/scene/fx'
import { dataFindings } from './parts/hook-data'

const WF = ['account_inquiry', 'card_support', 'dispute', 'credit'] as const
const BX = MX
const BW = 1680
const BY = 480
const BH = 110

export default defineScene({
  cues: [3.0, 6.4, 9.8, 13.4, 16.6],
  draw(env) {
    const { t, L, M, K } = env
    // ── arrive: the whole frame is data (light gray), counting in ─────────
    // At click 1 that field collapses into the contact bar: the rows become the chart.
    const fold = inOutCubic(seg(t, 3.05, 3.9))
    if (fold < 1) K.fillRR(lerp(-4, BX, fold), lerp(-4, BY, fold), lerp(W + 8, BW, fold), lerp(H + 8, BH, fold), 4 * fold, C.paper)
    K.fade(presence(t, 0.15, 3.1, 0.3, 0.2), () => {
      K.label(L('eyebrow'), MX, 300, { color: C.inkMute, alpha: outCubic(seg(t, 0.3, 0.8)) })
      const rows = M('data.rows_ingested')
      K.text(K.count(0, rows.num, seg(t, 0.3, 2.3), ','), MX, 610, { size: 190, weight: 800, fam: 'display', ls: -0.03, color: C.bg })
      K.words(L('rows'), MX, 710, { t, t0: 1.2, size: 44, weight: 500, fam: 'sans', color: C.inkDim, ls: -0.01 })
      K.label(`${M('data.tables').text} ${L('rowsSub')}`, MX, 780, { color: C.inkMute, alpha: outCubic(seg(t, 1.8, 2.3)) })
      source(K, rows, outCubic(seg(t, 1.8, 2.3)), undefined, C.inkMute)
    })
    // the evaluation dimensions: caption grey on the paper ground, then on ink once it folds
    if (fold < 1) dims(K, L('dims'), outCubic(seg(t, 0.3, 0.8)) * (1 - fold), C.inkMute)
    if (fold > 0) dims(K, L('dims'), fold, C.mute)

    // ── 1 share, then 2 the morph into first-contact resolution ──────────
    const shares = [...WF, 'other'].map((w) => M(`share.${w}`))
    const total = shares.reduce((a, m) => a + m.num, 0)
    const split = outCubic(seg(t, 3.9, 4.5))
    const m = inOutCubic(seg(t, 6.5, 7.6))
    const outBC = 1 - outCubic(seg(t, 9.85, 10.2))
    K.title(L('shareTitle'), t, 3.8, { tout: 6.45 })
    K.fade(presence(t, 4.0, 6.45) , () => {
      K.label(`${M('data.interactions').text} + ${M('data.complaints').text} ${L('shareSub')}  |  ${M('data.period').text}`, MX, 230)
    })
    let sx = BX
    shares.forEach((sh, i) => {
      const sw = (sh.num / total) * BW - 6 * split
      const grow = fold >= 1 ? 1 : 0
      const isOther = i === 4
      const fcr = isOther ? null : M(`fcr.${WF[i]}`)
      const colX = MX + i * 290
      const colH = fcr ? (fcr.num / 100) * 520 : 0
      const x = lerp(sx, colX, m)
      const w = lerp(sw * grow, 210, m)
      const h = lerp(BH, colH, m)
      const y = lerp(BY, 900 - colH, m)
      const isDispute = WF[i] === 'dispute'
      const col = isOther ? mix(C.paper, C.faint, split) : isDispute ? mix(C.paper, C.red, m) : mix(C.paper, C.dim, m * 0.7)
      const a = (isOther ? 1 - clamp(m * 2) : 1) * outBC
      if (grow > 0 && a > 0) K.fade(a, () => K.fillRR(x, y, w, h, 4, col))
      // share labels under the stacked bar
      K.fade(split * (1 - clamp(m * 3)) * outBC, () => {
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
      sx += sw + 6 * split
    })
    K.fade(presence(t, 3.6, 9.85), () => source(K, shares[0]))

    // the dispute panel, right of the columns
    K.title(L('fcrTitle'), t, 6.8, { tout: 9.85 })
    K.fade(outBC, () => {
      K.punch(L('fcrPunch'), t, 7.9, { x: 1320, y: 470, size: 48, maxW: 560, accent: C.red })
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

    // ── 3 what the data really holds: the pipeline and three findings ────
    K.title(L('txTitle'), t, 10.1, { tout: 13.45 })
    dataFindings(env, 10.0, 13.45)

    // ── 4 scope: four workflows, two languages ───────────────────────────
    const aE = outCubic(seg(t, 13.6, 13.9))
    K.title(L('scopeTitle'), t, 13.7)
    // four filled tiles rise from the baseline, each carrying its share and both languages
    K.fade(aE, () => {
      WF.forEach((w, i) => {
        const x = MX + i * 430
        const k = seg(t, 13.9 + i * 0.14, 14.6 + i * 0.14)
        field(K, x, 300, 390, 540, C.paper, k, 'bottom', 12)
        if (w === 'dispute') field(K, x, 300, 390, 14, C.red, seg(t, 14.6, 15.0), 'left', 4)
        const tk = outExpo(seg(t, 14.3 + i * 0.14, 14.9 + i * 0.14))
        K.fade(clamp(tk * 2), () => {
          const dy = (1 - tk) * 20
          K.wrap(L(w), 330, 38, 700, 'display').forEach((ln, j) => K.text(ln, x + 32, 384 + dy + j * 46, { size: 38, weight: 700, fam: 'display', color: C.bg }))
          K.text(M(`share.${w}`).text, x + 32, 610 + dy, { size: 64, weight: 800, fam: 'display', color: C.bg })
          K.label(L('ofContacts'), x + 32, 650 + dy, { size: 22, color: C.inkMute })
          K.text(L(`scope_${w}`), x + 32, 730 + dy, { size: 26, weight: 500, color: C.inkDim })
        })
        const lk = seg(t, 15.0 + i * 0.08, 15.4 + i * 0.08)
        const w1 = K.chip('es', x + 32, 764, { bg: C.bg, fg: C.paper, k: lk, size: 24, weight: 600 })
        K.chip('pt', x + 32 + w1 + 12, 764, { bg: C.bg, fg: C.paper, k: lk, size: 24, weight: 600 })
      })
    })
  },
})
