/**
 * Slide 3, architecture: a hexagonal backend with a deterministic core.
 *
 *   arrive  the core (yellow) inside a ring of ports
 *   1 kernel    what the policy kernel is: pure rules, clauses as data
 *   2 gateway   the LLM gateway (blue): a decorator stack, swappable providers
 *   3 verifier  every draft is checked; a violation falls back to a template
 *   4 data      the data platform and PostgreSQL with row-level security
 *   5 direction every edge points inward: imports flow to the core only
 *
 * The diagram on the left accumulates; the panel on the right swaps per click.
 */
import { defineScene } from '../lib/scene/types'
import { C, MX } from '../lib/scene/kit'
import { clamp, outCubic, presence, seg } from '../lib/scene/math'
import { check, cross, hex, node, tab, tag, type Tone } from '../lib/scene/bank'

const HC = { x: 700, y: 610 }
const PX = 1340
const PW = 460

type N = { key: string; x: number; y: number; w: number; tone: Tone; t0: number; from: [number, number]; to: [number, number] }
const NODES: readonly N[] = [
  { key: 'n_llm', x: MX, y: 330, w: 300, tone: 'blue', t0: 5.4, from: [420, 400], to: [506, 486] },
  { key: 'n_ret', x: MX, y: 800, w: 300, tone: 'blue', t0: 5.7, from: [420, 830], to: [506, 734] },
  { key: 'n_ver', x: 860, y: 250, w: 300, tone: 'yellow', t0: 8.6, from: [900, 346], to: [842, 400] },
  { key: 'n_db', x: 990, y: 562, w: 300, tone: 'paper', t0: 11.7, from: [990, 610], to: [974, 610] },
  { key: 'n_data', x: 860, y: 860, w: 340, tone: 'paper', t0: 11.5, from: [900, 860], to: [842, 820] },
]

export default defineScene({
  cues: [2.4, 5.2, 8.4, 11.4, 14.2, 17.0],
  draw({ t, L, M, K }) {
    K.title(L('title'), t, 0.1)
    K.fade(outCubic(seg(t, 1.5, 2.0)), () => K.cite(L('cite')))

    // ── the core and the ring of ports ────────────────────────────────────
    hex(K, HC.x, HC.y, 270, { k: outCubic(seg(t, 0.3, 1.3)), stroke: C.faint, lw: 3 })
    hex(K, HC.x, HC.y, 165, { k: outCubic(seg(t, 0.6, 1.6)), stroke: C.yellow, fill: C.yellowDeep, lw: 4 })
    K.fade(outCubic(seg(t, 1.3, 1.8)), () => {
      K.wrap(L('core'), 230, 26, 600).forEach((ln, i) => K.text(ln, HC.x, HC.y - 22 + i * 32, { size: 26, weight: 600, align: 'center' }))
      K.text(L('coreSub'), HC.x, HC.y + 50, { size: 22, weight: 500, fam: 'mono', color: C.yellow, align: 'center' })
      K.label(L('ports'), HC.x, 412, { size: 22, align: 'center' })
    })

    // ── edges: nodes, connectors, and at click 5 the inward arrows ───────
    const inward = (i: number) => outCubic(seg(t, 14.4 + i * 0.12, 14.8 + i * 0.12))
    NODES.forEach((n, i) => {
      const k = seg(t, n.t0, n.t0 + 0.6)
      node(K, n.x, n.y, n.w, 96, { label: L(n.key), sub: L(`${n.key}Sub`), tone: n.tone, k, size: 28 })
      const lk = outCubic(seg(t, n.t0 + 0.2, n.t0 + 0.6))
      if (lk > 0) K.line(n.from[0], n.from[1], n.from[0] + (n.to[0] - n.from[0]) * lk, n.from[1] + (n.to[1] - n.from[1]) * lk, C.faint, 3)
      const ak = inward(i)
      if (ak > 0) K.arrow(n.from[0], n.from[1], n.to[0], n.to[1], { color: C.dim, k: ak, lw: 3, head: 16 })
    })

    // ── the swapping panel ────────────────────────────────────────────────
    const head = (key: string, color: string, t0: number) =>
      K.words(L(key), PX, 330, { t, t0, size: 40, weight: 700, fam: 'display', color, stagger: 0.03 })
    const para = (s: string, y: number, t0: number, o: { size?: number; color?: string } = {}) => {
      const size = o.size ?? 28
      const lines = K.wrap(s, PW, size, 500)
      K.fade(outCubic(seg(t, t0, t0 + 0.4)), () =>
        lines.forEach((ln, i) => K.text(ln, PX, y + i * size * 1.35, { size, weight: 500, color: o.color ?? C.paper })))
      return lines.length * size * 1.35
    }

    // 1 policy kernel
    K.fade(presence(t, 2.5, 5.25, 0.3, 0.25), () => {
      head('p1h', C.yellow, 2.6)
      let y = 420
      for (const [key, t0] of [['p1a', 2.9], ['p1b', 3.2], ['p1c', 3.5]] as const) y += para(L(key), y, t0) + 24
    })

    // 2 LLM gateway: the decorator stack, outermost first, then providers
    K.fade(presence(t, 5.3, 8.45, 0.3, 0.25), () => {
      head('p2h', C.blueText, 5.5)
      for (let i = 0; i < 8; i++) {
        const k = outCubic(seg(t, 5.9 + i * 0.08, 6.3 + i * 0.08))
        K.fade(k, () => {
          K.fillRR(PX + i * 14, 392 + i * 38, 6, 26, 3, C.blue)
          K.text(L(`d${i + 1}`), PX + i * 14 + 22, 413 + i * 38, { size: 22, weight: 500, fam: 'mono', color: C.dim })
        })
      }
      let x = PX
      for (let i = 1; i <= 3; i++) x += tag(K, L(`prov${i}`), x, 720, { tone: 'blue', k: seg(t, 6.8 + i * 0.12, 7.2 + i * 0.12), size: 24 }) + 14
      para(L('p2c'), 820, 7.4, { size: 24, color: C.dim })
    })

    // 3 grounding verifier: draft, gate, send or template
    K.fade(presence(t, 8.5, 11.45, 0.3, 0.25), () => {
      head('p3h', C.yellow, 8.7)
      tag(K, L('draft'), PX, 400, { tone: 'blue', k: seg(t, 9.0, 9.4), size: 24 })
      K.arrow(PX + 40, 446, PX + 40, 486, { color: C.dim, k: outCubic(seg(t, 9.3, 9.6)) })
      tab(K, L('gate'), PX, 494, { tone: 'yellow', k: seg(t, 9.5, 9.9), size: 24 })
      check(K, PX + 30, 590, 30, seg(t, 9.9, 10.2), C.yellow, 5)
      K.fade(outCubic(seg(t, 10.0, 10.3)), () => K.text(L('send'), PX + 70, 600, { size: 28, weight: 600 }))
      cross(K, PX + 30, 670, 26, seg(t, 10.2, 10.5), C.red, 5)
      K.arrow(PX + 70, 670, PX + 140, 670, { color: C.dim, k: outCubic(seg(t, 10.4, 10.6)) })
      tab(K, L('template'), PX + 152, 650, { tone: 'yellow', k: seg(t, 10.5, 10.9), size: 24 })
      para(L('p3c'), 770, 10.8, { size: 24, color: C.dim })
    })

    // 4 data platform: the medallion layers and the row counts
    K.fade(presence(t, 11.5, 14.25, 0.3, 0.25), () => {
      head('p4h', C.paper, 11.7)
      let x = PX
      for (let i = 1; i <= 4; i++) {
        const w = tag(K, L(`s${i}`), x, 400, { tone: 'paper', k: seg(t, 11.9 + i * 0.12, 12.3 + i * 0.12), size: 22 })
        if (i < 4) K.arrow(x + w + 4, 420, x + w + 22, 420, { color: C.mute, lw: 2, head: 8, k: clamp(seg(t, 12.2 + i * 0.12, 12.4 + i * 0.12)) })
        x += w + 28
      }
      const rows = M('data.rows_ingested')
      const q = M('data.rows_quarantined')
      K.fade(outCubic(seg(t, 12.6, 13.0)), () => {
        K.text(rows.text, PX, 550, { size: 56, weight: 700, fam: 'display' })
        K.label(L('rowsIn'), PX, 590, { color: C.dim, size: 22 })
        K.text(q.text, PX, 690, { size: 56, weight: 700, fam: 'display' })
        K.label(L('rowsQ'), PX, 730, { color: C.dim, size: 22 })
      })
      para(L('p4c'), 800, 13.1, { size: 24, color: C.dim })
    })

    // 5 direction: ports the core owns
    K.fade(outCubic(seg(t, 14.3, 14.6)), () => {
      head('p5h', C.paper, 14.4)
      para(L('p5a'), 420, 14.7)
      for (let i = 0; i < 6; i++) {
        const k = seg(t, 15.2 + i * 0.1, 15.6 + i * 0.1)
        const col = i % 2
        tag(K, L(`port${i + 1}`), PX + col * 272, 560 + Math.floor(i / 2) * 62, { tone: 'paper', k, size: 22 })
      }
      para(L('p5c'), 790, 16.0, { size: 24, color: C.dim })
    })
  },
})
