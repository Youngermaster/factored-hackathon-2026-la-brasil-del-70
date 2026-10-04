/**
 * Slide 3, the architecture, on the deck's one light-gray ground (a blueprint
 * beat between dark slides). Three diagrams and one decision, one per click:
 *
 *   arrive  the stack: React, a FastAPI hexagonal core, PostgreSQL with RLS,
 *           the LiteLLM gateway to a provider named by settings, the data
 *           platform seeding PostgreSQL; a request travels it
 *   1       the deployment: one Azure VM, Docker Compose behind Caddy, the obs
 *           profile (collector, Prometheus, Grafana, Jaeger), the managed path
 *   2       the AI and ML path of one turn: which parts are models, which are
 *           code, and the risk estimate bouncing off the wall before the model
 *   3       the decision: learned components beat their baselines offline but
 *           not end to end, so the baselines stay the default
 *
 * Facts: README.md, deploy/README.md, ADR 0019, docs/models, docs/evaluation.
 */
import { defineScene } from '../lib/scene/types'
import { C, MX } from '../lib/scene/kit'
import { outCubic, presence, seg } from '../lib/scene/math'
import { dims, hex } from '../lib/scene/bank'
import { ground, packet } from '../lib/scene/fx'
import { box, wire } from './parts/arch-kit'
import { deployment } from './parts/arch-deploy'
import { mlPath } from './parts/arch-ml'
import { decision } from './parts/arch-decision'

const CUES = [3.0, 6.6, 10.4, 14.2] as const
const HC = { x: 960, y: 590 }

export default defineScene({
  cues: CUES,
  draw(env) {
    const { t, L, K } = env
    const c = [0, CUES[0] + 0.05, CUES[1] + 0.05, CUES[2] + 0.05]
    ground(K, C.paper)
    dims(K, L('dims'), outCubic(seg(t, 0.3, 0.8)), C.inkMute)
    ;(['t0', 't1', 't2', 't3'] as const).forEach((key, i) =>
      K.title(L(key), t, i ? c[i] + 0.1 : 0.1, { color: C.bg, tout: i < 3 ? c[i + 1] : undefined }))

    // ── arrive: the stack ──────────────────────────────────────────────────
    K.fade(presence(t, 0.1, c[1], 0.2, 0.25), () => {
      const k = (i: number) => seg(t, 0.25 + i * 0.1, 0.85 + i * 0.1)
      const web = box(K, 'ink', MX, 300, 380, 110, L('a_web'), L('a_webS'), k(0))
      const ml = box(K, 'ink', MX, 540, 380, 110, L('a_ml'), L('a_mlS'), k(1))
      const data = box(K, 'ink', MX, 800, 380, 110, L('a_data'), L('a_dataS'), k(2))
      const gw = box(K, 'blue', 1420, 300, 380, 110, L('a_gw'), L('a_gwS'), k(3))
      const prov = box(K, 'dashed', 1420, 540, 380, 110, L('a_prov'), L('a_provS'), k(4))
      const pg = box(K, 'ink', 1420, 800, 380, 110, L('a_pg'), L('a_pgS'), k(5))
      hex(K, HC.x, HC.y, 250, { k: outCubic(seg(t, 0.3, 1.2)), stroke: C.bg, lw: 2 })
      hex(K, HC.x, HC.y, 165, { k: outCubic(seg(t, 0.5, 1.3)), stroke: C.bg, fill: C.yellow, lw: 3 })
      K.fade(outCubic(seg(t, 1.0, 1.4)), () => {
        K.text(L('a_core'), HC.x, HC.y - 6, { size: 30, weight: 700, color: C.bg, align: 'center' })
        K.text(L('a_coreS'), HC.x, HC.y + 30, { size: 22, weight: 500, fam: 'mono', color: C.inkDim, align: 'center' })
        K.label(L('a_ports'), HC.x, HC.y - 236, { size: 22, color: C.inkMute, align: 'center' })
      })
      // connectors: every edge plugs into a port of the core
      const w = (i: number) => seg(t, 1.0 + i * 0.08, 1.4 + i * 0.08)
      wire(K, [{ x: web.r, y: web.cy }, { x: 760, y: 470 }], w(0))
      wire(K, [{ x: ml.r, y: ml.cy }, { x: 718, y: 590 }], w(1))
      wire(K, [{ x: 1162, y: 470 }, { x: gw.x, y: gw.cy }], w(2))
      wire(K, [{ x: gw.cx, y: gw.b }, { x: prov.cx, y: prov.y }], w(3))
      wire(K, [{ x: 1162, y: 710 }, { x: pg.x, y: pg.cy - 20 }], w(4))
      wire(K, [{ x: data.r, y: 878 }, { x: pg.x, y: 878 }], w(5))
      K.fade(outCubic(seg(t, 1.5, 1.8)), () => K.label(L('a_seed'), 960, 906, { size: 22, color: C.inkMute, align: 'center' }))
      // a request: browser to the core to its own rows; a model call; a seed row
      packet(K, [{ x: web.r, y: web.cy }, { x: 760, y: 470 }, { x: HC.x, y: HC.y }, { x: 1162, y: 710 }, { x: pg.x, y: pg.cy - 20 }], seg(t, 1.6, 2.6), C.bg, 9)
      packet(K, [{ x: 1162, y: 470 }, { x: gw.x, y: gw.cy }, { x: gw.cx, y: gw.cy }, { x: prov.cx, y: prov.y }], seg(t, 1.9, 2.8), C.blue, 9)
      packet(K, [{ x: data.r, y: 878 }, { x: pg.x, y: 878 }], seg(t, 2.0, 2.9), C.bg, 8)
      K.fade(outCubic(seg(t, 1.6, 2.0)), () => K.cite(L('cite0'), 1, C.inkMute))
    })

    deployment(env, c[1], c[2])
    mlPath(env, c[2], c[3])
    decision(env, c[3])
  },
})
