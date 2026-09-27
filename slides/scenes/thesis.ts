/**
 * Slide 2, the thesis: one customer turn through the five verbs of the brief.
 *
 *   arrive     a customer message types in (es-AR, with slang: "15 lucas")
 *   1 understand (blue)   words become structured fields
 *   2 decide     (yellow) clause-backed rules pass, one by one
 *   3 act+verify (yellow) the tool runs, the read-back confirms it
 *   4 injection  (red)    an instruction to act for another customer bounces
 *                         off the per-state tool allowlist
 *   5 escalate   (red)    a regulator mention: a structured handoff, no transcript
 *   6 the thesis line, one colour per clause
 *
 * The turn is illustrative; clause ids and parameters are the synthetic pack's.
 */
import { defineScene } from '../lib/scene/types'
import { C, MX, W } from '../lib/scene/kit'
import { outCubic, outExpo, presence, seg } from '../lib/scene/math'
import { bubble, check, cross, tab, tag } from '../lib/scene/bank'
import { clipWipe, field, packet, ring } from '../lib/scene/fx'

const X = [MX, 560, 1000, 1440] as const
const CW = 360
const HY = 480
const CAPY = 900
const BY = 220

export default defineScene({
  cues: [2.4, 5.4, 8.4, 11.4, 14.6, 17.6, 20.4],
  draw({ t, L, M, K }) {
    const fin = outCubic(seg(t, 17.7, 18.3))
    const dimAll = 1 - fin
    // each phase owns a filled header in its colour, ink text on top (AA: ink on blue 4.8,
    // on yellow 13.0, on red 4.4 at 30 px bold, which is large text)
    const heading = (i: number, key: string, fill: string, t0: number) => {
      field(K, X[i], HY - 52, 400, 72, fill, seg(t, t0 - 0.1, t0 + 0.35), 'left', 8)
      K.words(L(key), X[i] + 22, HY - 4, { t, t0: t0 + 0.12, size: 30, weight: 700, fam: 'display', color: C.bg, accent: C.bg, stagger: 0.03 })
    }
    const caption = (i: number, s: string, color: string, t0: number) =>
      K.wrap(s, 410, 22, 500, 'mono').forEach((ln, j) =>
        K.label(ln, X[i], CAPY + j * 30, { color, size: 22, alpha: outCubic(seg(t, t0, t0 + 0.4)) }))

    K.fade(dimAll, () => {
      K.title(L('title'), t, 0.1)
      // ── arrive: the customer message ───────────────────────────────────
      const msg = L('msg')
      K.fade(1 - 0.65 * outCubic(seg(t, 11.5, 11.9)), () => {
        bubble(K, msg, MX, BY, { typed: seg(t, 0.5, 1.9), k: seg(t, 0.3, 0.9), size: 32, maxW: 1000, label: L('who') })
        // 1: the words the model reads, underlined in blue
        const base = BY + 24 + 32 * 0.95 + 12
        for (const [key, t0] of [['hl1', 2.5], ['hl2', 2.7]] as const) {
          const s = L(key)
          const x0 = MX + 32 + K.measure(msg.slice(0, msg.indexOf(s)), 32, 500, 'sans')
          const w = K.measure(s, 32, 500, 'sans')
          const k = outExpo(seg(t, t0, t0 + 0.4))
          if (k > 0) K.line(x0, base, x0 + w * k, base, C.blue, 4)
          // the underlined words travel down into the understand header
          const cx = x0 + w / 2
          packet(K, [{ x: cx, y: base + 6 }, { x: cx, y: 360 }, { x: 250, y: 410 }], seg(t, t0 + 0.35, t0 + 0.95), C.blue, 9)
        }
      })
      K.fade(outCubic(seg(t, 1.4, 1.9)), () => K.cite(L('footnote')))

      // ── 1 understand ─────────────────────────────────────────────────────
      K.arrow(250, BY + 100, 250, 414, { color: C.blue, k: outCubic(seg(t, 2.9, 3.3)) })
      heading(0, 'understand', C.blue, 3.2)
      ;(['x_intent', 'x_reason', 'x_amount', 'x_lang'] as const).forEach((key, i) =>
        tag(K, L(key), X[0], 530 + i * 64, { tone: 'blue', k: seg(t, 3.6 + i * 0.15, 4.0 + i * 0.15), size: 24 }))
      caption(0, L('capUnderstand'), C.blueText, 4.6)

      // ── 2 decide ─────────────────────────────────────────────────────────
      K.arrow(X[0] + CW + 10, 640, X[1] - 16, 640, { color: C.yellow, k: outCubic(seg(t, 5.5, 5.8)) })
      packet(K, [{ x: X[0] + CW + 10, y: 640 }, { x: X[1] - 10, y: 640 }], seg(t, 5.55, 6.0), C.blue, 8)
      heading(1, 'decide', C.yellow, 5.6)
      const rules = [
        [L('r_status'), L('r_statusId')],
        [`${L('r_window')} ${M('policy.dispute_window_ar').text}`, L('r_windowId')],
        [L('r_reason'), L('r_reasonId')],
        [`${L('r_amount')} ${M('policy.auto_limit_ar').text}`, L('r_amountId')],
      ] as const
      rules.forEach(([txt, id], i) => {
        const t0 = 6.0 + i * 0.35
        const y = 540 + i * 80
        check(K, X[1] + 14, y - 10, 26, seg(t, t0, t0 + 0.3), C.yellow, 5)
        K.fade(outCubic(seg(t, t0 + 0.1, t0 + 0.4)), () => {
          K.text(txt, X[1] + 48, y, { size: 26, weight: 500 })
          K.text(id, X[1] + 48, y + 32, { size: 22, weight: 500, fam: 'mono', color: C.yellow })
        })
      })
      caption(1, L('capDecide'), C.yellow, 7.6)

      // ── 3 act and verify ─────────────────────────────────────────────────
      K.arrow(X[1] + CW + 10, 640, X[2] - 16, 640, { color: C.yellow, k: outCubic(seg(t, 8.5, 8.8)) })
      heading(2, 'act', C.yellow, 8.6)
      packet(K, [{ x: X[1] + CW + 10, y: 640 }, { x: X[2] - 10, y: 640 }], seg(t, 8.55, 9.0), C.yellow, 8)
      // the act column, drawn twice: on the dark ground, then in ink inside the
      // yellow field that floods the column the moment the read-back verifies
      const AX = X[2] + 20
      const act = (inked: boolean) => {
        const fg = inked ? C.bg : C.yellow
        const chip = (s: string, y: number, k: number, size: number, x: number = AX) => inked
          ? K.chip(s, x, y, { bg: C.bg, fg: C.yellow, k, size, weight: 700 })
          : tab(K, s, x, y, { tone: 'yellow', k, size })
        chip(L('tool'), 520, seg(t, 9.0, 9.4), 24)
        const lk = outCubic(seg(t, 9.3, 9.7))
        if (lk > 0) {
          K.line(AX + 20, 575, AX + 20, 575 + 70 * lk, fg, 3)
          K.dot(AX + 20, 575 + 70 * lk, 7, fg)
        }
        check(K, AX + 18, 680, 26, seg(t, 9.8, 10.1), fg, 5)
        K.fade(outCubic(seg(t, 9.9, 10.2)), () => K.text(L('readback'), AX + 48, 690, { size: 26, weight: 500, color: inked ? C.bg : C.paper }))
        chip(L('verified'), 716, seg(t, 10.2, 10.6), 22, AX + 48)
        K.fade(outCubic(seg(t, 10.5, 10.9)), () =>
          K.text(`${L('reply')} ${M('policy.dispute_sla_ar').text}`, AX, 830, { size: 24, weight: 500, color: inked ? C.inkDim : C.dim }))
      }
      act(false)
      ring(K, AX + 18, 680, seg(t, 9.85, 10.45), C.yellow, 10, 110)
      const fk = seg(t, 10.0, 10.5)
      field(K, X[2], 504, 400, 360, C.yellow, fk, 'bottom', 12)
      clipWipe(K, X[2], 504, 400, 360, fk, 'bottom', () => act(true))
      caption(2, L('capAct'), C.yellow, 10.8)

      // ── 4 injection: bounces off the allowlist ──────────────────────────
      K.fade(presence(t, 11.6, 14.7, 0.3, 0.3), () =>
        bubble(K, L('injMsg'), 1800, BY, { typed: seg(t, 11.7, 12.5), k: seg(t, 11.6, 12.1), size: 32, maxW: 760, align: 'right', tone: 'red', label: L('who') }))
      const bk = outCubic(seg(t, 12.5, 12.9))
      if (bk > 0) {
        K.fillRR(560, 398, 1240 * bk, 12, 6, C.yellow)
        K.label(L('barrier'), 1800, 384, { color: C.yellow, align: 'right', alpha: outCubic(seg(t, 12.8, 13.1)) })
      }
      // the packet: falls, hits the barrier at 13.0, recoils and fades
      if (t > 12.6 && t < 13.6) {
        const down = outCubic(seg(t, 12.6, 13.0))
        const up = outCubic(seg(t, 13.0, 13.5))
        const y = 350 + 48 * down - 70 * up
        K.fade(1 - seg(t, 13.2, 13.6), () => K.dot(1300, y, 14, C.red))
      }
      ring(K, 1300, 398, seg(t, 13.0, 13.6), C.red, 10, 90)
      cross(K, 1300, 405, 34, seg(t, 13.0, 13.3) * (1 - seg(t, 14.7, 15.0)), C.red, 6)
      K.fade(presence(t, 13.3, 14.7, 0.3, 0.3), () => {
        const w = tab(K, L('injTag'), 560, 344, { tone: 'red', k: seg(t, 13.3, 13.7), size: 24 })
        K.label(L('injCap'), 560 + w + 20, 372, { color: C.redText, size: 22 })
      })

      // ── 5 escalate: a structured handoff ─────────────────────────────────
      K.fade(outCubic(seg(t, 14.8, 15.2)), () =>
        bubble(K, L('escMsg'), 1800, BY, { typed: seg(t, 14.9, 15.6), k: seg(t, 14.8, 15.3), size: 32, maxW: 760, align: 'right', label: L('who') }))
      K.arrow(X[2] + CW + 10, 640, X[3] - 16, 640, { color: C.red, k: outCubic(seg(t, 15.4, 15.7)) })
      heading(3, 'escalate', C.red, 15.5)
      tag(K, L('escTrigger'), X[3], 510, { tone: 'red', k: seg(t, 15.7, 16.1), size: 24 })
      const ck = outExpo(seg(t, 15.9, 16.5))
      if (ck > 0) {
        K.fade(ck, () => K.fillRR(X[3], 574, CW, 236, 10, C.redDeep))
        ;(['h_request', 'h_facts', 'h_actions', 'h_evidence', 'h_open'] as const).forEach((key, i) =>
          K.fade(outCubic(seg(t, 16.1 + i * 0.12, 16.4 + i * 0.12)), () => {
            K.fillRR(X[3] + 22, 602 + i * 42, 12, 4, 2, C.red)
            K.text(L(key), X[3] + 48, 612 + i * 42, { size: 24, weight: 500 })
          }))
      }
      K.fade(outCubic(seg(t, 16.9, 17.2)), () => {
        K.text(L('h_transcript'), X[3] + 48, 850, { size: 24, weight: 500, color: C.mute })
        K.line(X[3] + 44, 842, X[3] + 48 + K.measure(L('h_transcript'), 24, 500) * outCubic(seg(t, 17.0, 17.3)) + 4, 842, C.red, 3)
      })
      caption(3, `${L('capEscalate')} ${M('policy.handoff_sla_ar').text}`, C.redText, 17.1)
    })

    // ── 6 the thesis: three full-width bands, one per clause ───────────────
    const bands = [['t1', C.blue], ['t2', C.yellow], ['t3', C.paper]] as const
    bands.forEach(([key, fill], i) => {
      const y = 250 + i * 180
      field(K, -4, y, W + 8, 180, fill, seg(t, 17.8 + i * 0.3, 18.4 + i * 0.3), 'left')
      K.words(L(key), MX, y + 112, { t, t0: 18.05 + i * 0.3, size: 64, weight: 800, fam: 'display', color: C.bg, accent: C.bg, stagger: 0.04 })
    })
  },
})
