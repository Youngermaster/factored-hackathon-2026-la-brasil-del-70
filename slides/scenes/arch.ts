/**
 * Slide 3, architecture, on the deck's one light-gray ground (a blueprint
 * beat between two dark slides). Colours keep their meaning: the core is
 * yellow, the model edges blue, data and stores ink.
 *
 *   arrive  the yellow core inside a ring of ports
 *   1 kernel    a clause file becomes a rule call becomes a Decision
 *   2 gateway   a request falls through the decorator stack to a provider
 *   3 verifier  a grounded draft is sent; an unsupported one becomes a template
 *   4 data      rows flow raw to gold; bad rows drop into quarantine
 *   5 direction packets flow inward along every edge
 *
 * The diagram on the left accumulates; the panel on the right swaps per click.
 */
import { defineScene } from '../lib/scene/types'
import { C, MX } from '../lib/scene/kit'
import { hash, outCubic, presence, seg } from '../lib/scene/math'
import { hex, node, type Tone } from '../lib/scene/bank'
import { ground, packet } from '../lib/scene/fx'
import { panels } from './parts/arch-panels'

const HC = { x: 700, y: 610 }

type N = { key: string; x: number; y: number; w: number; tone: Tone; ink?: boolean; t0: number; from: [number, number]; to: [number, number] }
const NODES: readonly N[] = [
  { key: 'n_llm', x: MX, y: 330, w: 300, tone: 'blue', t0: 5.4, from: [420, 400], to: [506, 486] },
  { key: 'n_ret', x: MX, y: 800, w: 300, tone: 'blue', t0: 5.7, from: [420, 830], to: [506, 734] },
  { key: 'n_ver', x: 860, y: 250, w: 300, tone: 'yellow', t0: 8.6, from: [900, 346], to: [842, 400] },
  { key: 'n_db', x: 990, y: 562, w: 300, tone: 'paper', ink: true, t0: 11.7, from: [990, 610], to: [974, 610] },
  { key: 'n_data', x: 860, y: 860, w: 340, tone: 'paper', ink: true, t0: 11.5, from: [900, 860], to: [842, 820] },
]

export default defineScene({
  cues: [2.4, 5.2, 8.4, 11.4, 14.2, 17.0],
  draw(env) {
    const { t, L, K } = env
    ground(K, C.paper)
    K.title(L('title'), t, 0.1, { color: C.bg })
    K.fade(outCubic(seg(t, 1.5, 2.0)), () => K.cite(L('cite'), 1, C.inkMute))

    // ── the core and the ring of ports ────────────────────────────────────
    hex(K, HC.x, HC.y, 270, { k: outCubic(seg(t, 0.3, 1.3)), stroke: C.bg, lw: 3 })
    hex(K, HC.x, HC.y, 165, { k: outCubic(seg(t, 0.6, 1.6)), stroke: C.bg, fill: C.yellow, lw: 4 })
    K.fade(outCubic(seg(t, 1.3, 1.8)), () => {
      K.wrap(L('core'), 230, 28, 700).forEach((ln, i) => K.text(ln, HC.x, HC.y - 22 + i * 34, { size: 28, weight: 700, align: 'center', color: C.bg }))
      K.text(L('coreSub'), HC.x, HC.y + 52, { size: 22, weight: 500, fam: 'mono', color: C.inkDim, align: 'center' })
      K.label(L('ports'), HC.x, 412, { size: 22, align: 'center', color: C.inkMute })
    })

    // ── edges: filled nodes, connectors, and at click 5 inward packets ───
    NODES.forEach((n, i) => {
      const k = seg(t, n.t0, n.t0 + 0.6)
      if (n.ink) {
        K.fade(outCubic(k), () => {
          K.fillRR(n.x, n.y, n.w, 96, 10, C.bg)
          K.text(L(n.key), n.x + 30, n.y + 42, { size: 28, weight: 600, color: C.paper })
          K.text(L(`${n.key}Sub`), n.x + 30, n.y + 78, { size: 22, weight: 500, fam: 'mono', color: C.dim })
        })
      }
      else node(K, n.x, n.y, n.w, 96, { label: L(n.key), sub: L(`${n.key}Sub`), tone: n.tone, k, size: 28, filled: true })
      const lk = outCubic(seg(t, n.t0 + 0.2, n.t0 + 0.6))
      if (lk > 0) K.line(n.from[0], n.from[1], n.from[0] + (n.to[0] - n.from[0]) * lk, n.from[1] + (n.to[1] - n.from[1]) * lk, C.bg, 3)
      const ak = outCubic(seg(t, 14.4 + i * 0.12, 14.8 + i * 0.12))
      if (ak > 0) K.arrow(n.from[0], n.from[1], n.to[0], n.to[1], { color: C.bg, k: ak, lw: 4, head: 18 })
      const path = [{ x: n.from[0], y: n.from[1] }, { x: n.to[0], y: n.to[1] }]
      const pc = n.tone === 'paper' ? C.bg : n.tone === 'blue' ? C.blue : C.yellow
      for (let j = 0; j < 2; j++) packet(K, path, seg(t, 14.6 + i * 0.1 + j * 0.35 + hash(i, j) * 0.1, 15.3 + i * 0.1 + j * 0.35), pc, 8)
    })

    panels(env)
    void presence
  },
})
