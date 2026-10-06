/**
 * Pitch slide 2 (static): the product, one customer turn as a glass box.
 *
 * The four phases of the video deck's thesis scene at rest, side by side:
 * understand (blue: the model extracts fields), decide (yellow: rules and
 * clauses), act and verify (yellow: a verified write), escalate (red: a
 * structured handoff). Above them, an injection bounces off the per-state
 * tool allowlist; below, the thesis line.
 */
import { defineScene } from '../lib/scene/types'
import { C, MX } from '../lib/scene/kit'
import { bubble, check, dims, tab, tag } from '../lib/scene/bank'
import { S, citeFit, ptitle } from './parts/pitch-kit'

const CW = 380
const X = [MX, MX + 427, MX + 853, MX + 1280] as const

export default defineScene({
  cues: [30],
  draw({ L, M, K }) {
    const T = S.thesis
    dims(K, T('dims'))
    ptitle(K, L('title'))

    // ── the customer turn and the injection ───────────────────────────────
    bubble(K, T('msg'), MX, 212, { size: 30, maxW: 820, label: T('who') })
    bubble(K, T('injMsg'), 1800, 212, { size: 28, maxW: 760, align: 'right', tone: 'red', label: T('who') })
    K.arrow(X[0] + 130, 312, X[0] + 130, 420, { color: C.blue, lw: 3, head: 12 })
    const w = tab(K, T('injTag'), X[1], 340, { tone: 'red', size: 22 })
    K.label(T('injCap'), X[1] + w + 18, 364, { color: C.redText, size: 22 })
    K.label(T('barrier'), 1800, 380, { color: C.yellow, align: 'right' })
    K.fillRR(X[1], 396, 1800 - X[1], 10, 5, C.yellow)

    // ── the four phase headers ────────────────────────────────────────────
    const heads = [['understand', C.blue], ['decide', C.yellow], ['act', C.yellow], ['escalate', C.red]] as const
    heads.forEach(([key, color], i) => {
      K.fillRR(X[i], 424, CW, 68, 6, color)
      K.text(T(key), X[i] + 22, 470, { size: 30, weight: 700, fam: 'display', color: C.bg })
      if (i < 3) K.arrow(X[i] + CW + 8, 650, X[i + 1] - 8, 650, { color: i === 2 ? C.red : i === 0 ? C.yellow : C.yellow, lw: 3, head: 10 })
    })

    // understand: the fields the model extracts, schema-checked
    ;(['x_intent', 'x_reason', 'x_amount', 'x_lang'] as const).forEach((key, i) =>
      tag(K, T(key), X[0], 516 + i * 64, { tone: 'blue', size: 24 }))

    // decide: every rule with its clause id
    const rules = [
      [T('r_status'), T('r_statusId')],
      [`${T('r_window')} ${M('policy.dispute_window_ar').text}`, T('r_windowId')],
      [T('r_reason'), T('r_reasonId')],
      [`${T('r_amount')} ${M('policy.auto_limit_ar').text}`, T('r_amountId')],
    ] as const
    rules.forEach(([txt, id], i) => {
      const y = 540 + i * 80
      check(K, X[1] + 14, y - 10, 26, 1, C.yellow, 5)
      K.text(txt, X[1] + 48, y, { size: 26, weight: 500 })
      K.text(id, X[1] + 48, y + 32, { size: 22, weight: 500, fam: 'mono', color: C.yellow })
    })

    // act and verify: the write, then the read-back that proves it
    K.fillRR(X[2], 508, CW, 352, 10, C.yellow)
    K.chip(T('tool'), X[2] + 20, 524, { bg: C.bg, fg: C.yellow, size: 24, weight: 700 })
    K.line(X[2] + 40, 572, X[2] + 40, 640, C.bg, 3)
    K.dot(X[2] + 40, 644, 7, C.bg)
    check(K, X[2] + 38, 686, 26, 1, C.bg, 5)
    K.text(T('readback'), X[2] + 68, 696, { size: 26, weight: 500, color: C.bg })
    K.chip(T('verified'), X[2] + 68, 722, { bg: C.bg, fg: C.yellow, size: 22, weight: 600 })
    K.text(`${T('reply')} ${M('policy.dispute_sla_ar').text}`, X[2] + 20, 832, { size: 22, weight: 500, color: C.inkDim })

    // escalate: the trigger and the structured handoff, never the transcript
    K.label(`"${T('escMsg')}"`, X[3], 520, { size: 19, color: C.dim })
    tag(K, T('escTrigger'), X[3], 538, { tone: 'red', size: 22 })
    K.fillRR(X[3], 594, CW, 222, 10, C.redDeep)
    ;(['h_request', 'h_facts', 'h_actions', 'h_evidence', 'h_open'] as const).forEach((key, i) => {
      K.fillRR(X[3] + 22, 622 + i * 40, 12, 4, 2, C.red)
      K.text(T(key), X[3] + 48, 632 + i * 40, { size: 24, weight: 500 })
    })
    K.text(T('h_transcript'), X[3] + 48, 850, { size: 24, weight: 500, color: C.mute })
    const tw = K.measure(T('h_transcript'), 24, 500, 'sans')
    K.line(X[3] + 42, 842, X[3] + 54 + tw, 842, C.red, 3)

    // the captions: what each colour is
    const caps = [
      ['capUnderstand', C.blueText, ''],
      ['capDecide', C.yellow, ''],
      ['capAct', C.yellow, ''],
      ['capEscalate', C.redText, ` ${M('policy.handoff_sla_ar').text}`],
    ] as const
    caps.forEach(([key, color, extra], i) =>
      K.wrap(`${T(key)}${extra}`, CW, 22, 500, 'mono').forEach((ln, j) =>
        K.text(ln, X[i], 900 + j * 28, { size: 22, weight: 500, fam: 'mono', color })))

    // the thesis line
    K.words(`${T('t1')} ${T('t2')} ${T('t3')}`, MX, 984, { t: 30, t0: 0, size: 34, weight: 600, fam: 'sans', ls: -0.01, accent: C.yellow, maxW: 1700 })
    citeFit(K, T('footnote'))
    void L
  },
})
