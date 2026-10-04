/**
 * Click 2 of the architecture scene: the AI and ML path of one turn.
 *
 *   row 1  a message, the language model (understanding only), the intent
 *          router, the workflow state machine with the policy kernel, the
 *          verified tools
 *   row 2  the transaction resolver feeds the workflow; credit's risk
 *          estimate feeds the synthetic eligibility service and bounces off
 *          the wall in front of the model (never sent to it)
 *   row 3  the reply: a template, or model phrasing, through the grounding
 *          verifier before the customer sees it
 *
 * Every learned component names its served baseline first, then the learned
 * alternative a setting selects (docs/models).
 */
import type { SceneEnv } from '../../lib/scene/types'
import { C, MX } from '../../lib/scene/kit'
import { outCubic, outExpo, presence, seg } from '../../lib/scene/math'
import { packet, ring } from '../../lib/scene/fx'
import { cross } from '../../lib/scene/bank'
import { box, wire } from './arch-kit'

export function mlPath({ t, L, K }: SceneEnv, c2: number, tout: number) {
  K.fade(presence(t, c2, tout, 0.3, 0.25), () => {
    const k = (i: number) => seg(t, c2 + 0.2 + i * 0.12, c2 + 0.8 + i * 0.12)
    const msg = box(K, 'dashed', MX, 300, 200, 110, L('c_msg'), L('c_msgS'), k(0), 26)
    const llm = box(K, 'blue', 370, 300, 300, 110, L('c_llm'), L('c_llmS'), k(1))
    const rtr = box(K, 'blue', 720, 300, 320, 110, L('c_rtr'), L('c_rtrS'), k(2))
    const wf = box(K, 'yellow', 1090, 300, 330, 110, L('c_wf'), L('c_wfS'), k(3))
    const tools = box(K, 'yellow', 1470, 300, 330, 110, L('c_tools'), L('c_toolsS'), k(4))
    const res = box(K, 'blue', 720, 530, 320, 110, L('c_res'), L('c_resS'), k(5))
    const risk = box(K, 'ink', 1090, 530, 330, 110, L('c_risk'), L('c_riskS'), k(6))
    const elg = box(K, 'yellow', 1470, 530, 330, 110, L('c_elg'), L('c_elgS'), k(7))
    const w = (i: number) => seg(t, c2 + 0.9 + i * 0.08, c2 + 1.2 + i * 0.08)
    wire(K, [{ x: msg.r, y: 355 }, { x: llm.x, y: 355 }], w(0))
    wire(K, [{ x: llm.r, y: 355 }, { x: rtr.x, y: 355 }], w(1))
    wire(K, [{ x: rtr.r, y: 355 }, { x: wf.x, y: 355 }], w(2))
    wire(K, [{ x: wf.r, y: 355 }, { x: tools.x, y: 355 }], w(3))
    wire(K, [{ x: res.r, y: 585 }, { x: 1065, y: 585 }, { x: 1065, y: wf.b + 4 }], w(4))
    wire(K, [{ x: wf.cx, y: wf.b }, { x: wf.cx, y: risk.y }], w(5))
    wire(K, [{ x: risk.r, y: 585 }, { x: elg.x, y: 585 }], w(6))
    // the turn: understanding (blue), then code deciding and acting (yellow)
    packet(K, [{ x: msg.r, y: 355 }, { x: rtr.cx, y: 355 }, { x: wf.cx, y: 355 }, { x: tools.cx, y: 355 }], seg(t, c2 + 1.3, c2 + 2.3), C.blue, 9)
    // credit: the estimate reaches eligibility, and its copy toward the model bounces off the wall
    packet(K, [{ x: risk.r, y: 585 }, { x: elg.x + 20, y: 585 }], seg(t, c2 + 2.0, c2 + 2.4), C.bg, 9)
    // the wall sits in the gap between the rows, right of the model
    const WY = 470
    const wk = outExpo(seg(t, c2 + 1.9, c2 + 2.2))
    if (wk > 0) K.fillRR(694, WY - 42 * wk, 12, 84 * wk, 6, C.red)
    if (t > c2 + 2.1 && t < c2 + 2.9) {
      const go = outCubic(seg(t, c2 + 2.1, c2 + 2.5))
      const back = outCubic(seg(t, c2 + 2.5, c2 + 2.9))
      K.fade(1 - seg(t, c2 + 2.6, c2 + 2.9), () => K.dot(risk.x + 30 - 330 * go + 50 * back, WY, 10, C.bg))
    }
    ring(K, 700, WY, seg(t, c2 + 2.5, c2 + 3.0), C.red, 10, 70)
    // at rest the blocked path stays drawn: a dashed line from the estimator that ends in a cross at the wall
    K.fade(outCubic(seg(t, c2 + 2.6, c2 + 3.0)), () => {
      K.line(risk.x + 30, risk.y, risk.x + 30, WY, C.inkMute, 2, [8, 7])
      K.line(risk.x + 30, WY, 716, WY, C.inkMute, 2, [8, 7])
    })
    cross(K, 736, WY, 18, seg(t, c2 + 2.5, c2 + 2.8), C.red, 4)
    K.fade(outCubic(seg(t, c2 + 2.4, c2 + 2.7)), () => {
      K.text(L('c_wall'), MX, WY - 4, { size: 24, weight: 600, color: C.bg })
      K.label(L('c_wallS'), MX, WY + 30, { size: 22, color: C.inkDim })
    })
    // the reply: a template, or phrasing from the model, checked before it is sent
    const r = (i: number) => seg(t, c2 + 2.3 + i * 0.12, c2 + 2.8 + i * 0.12)
    const draft = box(K, 'blue', 370, 770, 330, 110, L('c_draft'), L('c_draftS'), r(0))
    const ver = box(K, 'yellow', 760, 770, 330, 110, L('c_ver'), L('c_verS'), r(1))
    const out = box(K, 'dashed', 1150, 770, 280, 110, L('c_out'), L('c_outS'), r(2), 26)
    wire(K, [{ x: draft.r, y: 825 }, { x: ver.x, y: 825 }], r(1))
    wire(K, [{ x: ver.r, y: 825 }, { x: out.x, y: 825 }], r(2))
    packet(K, [{ x: draft.r, y: 825 }, { x: out.x, y: 825 }], seg(t, c2 + 2.9, c2 + 3.5), C.bg, 8)
    K.fade(outCubic(seg(t, c2 + 2.6, c2 + 3.0)), () => K.text(L('c_gw'), 1480, 815, { size: 24, weight: 600, color: C.bg }))
    K.fade(outCubic(seg(t, c2 + 2.7, c2 + 3.1)), () => K.label(L('c_gwS'), 1480, 850, { size: 22, color: C.inkDim }))
    K.fade(outCubic(seg(t, c2 + 1.0, c2 + 1.4)), () => K.cite(L('cite2'), 1, C.inkMute))
  })
}
