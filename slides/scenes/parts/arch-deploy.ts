/**
 * Click 1 of the architecture scene: the deployment as it runs today.
 *
 * One Azure VM, one Docker Compose project: Caddy terminates TLS and serves
 * the SPA, the API runs two workers, PostgreSQL sits on the internal network,
 * and one-shot jobs migrate, seed and purge. The obs profile switches on
 * beside them (collector, Prometheus, Grafana, Jaeger). The model is hosted,
 * reached through LiteLLM over https. Below, the documented path to managed
 * services (ADR 0019); Key Vault secrets are in review (PR 27).
 */
import type { SceneEnv } from '../../lib/scene/types'
import { C, MX } from '../../lib/scene/kit'
import { outCubic, presence, seg } from '../../lib/scene/math'
import { packet } from '../../lib/scene/fx'
import { box, region, wire } from './arch-kit'

const VM = { x: 380, y: 250, w: 1100, h: 640 }

export function deployment({ t, L, K }: SceneEnv, c1: number, tout: number) {
  K.fade(presence(t, c1, tout, 0.3, 0.25), () => {
    const k = (i: number) => seg(t, c1 + 0.2 + i * 0.1, c1 + 0.8 + i * 0.1)
    region(K, VM.x, VM.y, VM.w, VM.h, L('b_vm'), seg(t, c1 + 0.1, c1 + 0.6), false)
    const net = box(K, 'dashed', MX, 340, 200, 100, L('b_net'), L('b_netS'), k(0), 26)
    const caddy = box(K, 'ink', 420, 320, 300, 120, L('b_caddy'), L('b_caddyS'), k(1))
    const api = box(K, 'yellow', 770, 320, 300, 120, L('b_api'), L('b_apiS'), k(2))
    const pg = box(K, 'ink', 1120, 320, 320, 120, L('b_pg'), L('b_pgS'), k(3))
    K.chip(L('b_jobs'), 1120, 460, { bg: C.bg, fg: C.paper, size: 22, weight: 600, k: k(4) })
    const prov = box(K, 'blue', 1530, 320, 270, 120, L('b_prov'), L('b_provS'), k(5), 26)
    wire(K, [{ x: net.r, y: 390 }, { x: caddy.x, y: 390 }], k(1))
    wire(K, [{ x: caddy.r, y: 380 }, { x: api.x, y: 380 }], k(2))
    wire(K, [{ x: api.r, y: 380 }, { x: pg.x, y: 380 }], k(3))
    wire(K, [{ x: api.cx, y: api.y }, { x: api.cx, y: 290 }, { x: prov.cx, y: 290 }, { x: prov.cx, y: prov.y }], k(5), C.blue)
    // a request: internet, TLS, the API, its own rows; then a model call
    packet(K, [{ x: net.r, y: 390 }, { x: api.cx, y: 380 }, { x: pg.cx, y: 380 }], seg(t, c1 + 1.0, c1 + 1.8), C.bg, 9)
    packet(K, [{ x: api.cx, y: api.y }, { x: api.cx, y: 290 }, { x: prov.cx, y: 290 }, { x: prov.cx, y: prov.y }], seg(t, c1 + 1.5, c1 + 2.2), C.blue, 9)

    // the obs profile switches on: telemetry flows from the API
    const ok = seg(t, c1 + 1.4, c1 + 1.9)
    region(K, 420, 560, 1020, 300, L('b_obs'), ok, true, true)
    const o = (i: number) => seg(t, c1 + 1.6 + i * 0.1, c1 + 2.1 + i * 0.1)
    const col = box(K, 'ink', 450, 700, 220, 110, L('b_col'), L('b_colS'), o(0), 26)
    const prom = box(K, 'ink', 700, 700, 220, 110, L('b_prom'), L('b_promS'), o(1), 26)
    const graf = box(K, 'ink', 950, 700, 220, 110, L('b_graf'), L('b_grafS'), o(2), 26)
    const jae = box(K, 'ink', 1200, 700, 220, 110, L('b_jae'), L('b_jaeS'), o(3), 26)
    wire(K, [{ x: api.cx, y: api.b }, { x: api.cx, y: 520 }, { x: col.cx, y: 520 }, { x: col.cx, y: col.y }], o(0))
    wire(K, [{ x: col.r, y: 755 }, { x: prom.x, y: 755 }], o(1))
    wire(K, [{ x: prom.r, y: 755 }, { x: graf.x, y: 755 }], o(2))
    wire(K, [{ x: col.cx + 60, y: col.y }, { x: col.cx + 60, y: 660 }, { x: jae.cx, y: 660 }, { x: jae.cx, y: jae.y }], o(3))
    for (let j = 0; j < 2; j++) {
      const s = c1 + 2.2 + j * 0.3
      packet(K, [{ x: api.cx, y: api.b }, { x: api.cx, y: 520 }, { x: col.cx, y: 520 }, { x: col.cx, y: 755 }, { x: graf.x, y: 755 }], seg(t, s, s + 0.9), C.bg, 8)
    }
    packet(K, [{ x: col.cx + 60, y: col.y }, { x: col.cx + 60, y: 660 }, { x: jae.cx, y: 660 }, { x: jae.cx, y: jae.y }], seg(t, c1 + 2.5, c1 + 3.2), C.bg, 8)

    // the documented path to managed services
    K.fade(outCubic(seg(t, c1 + 2.6, c1 + 3.0)), () => {
      K.label(L('b_next'), MX, 952, { size: 22, color: C.inkMute })
      let x = MX + K.measure(L('b_next'), 22, 500, 'mono') + 24
      for (const key of ['b_m1', 'b_m2', 'b_m3'] as const) {
        K.ctx.save()
        K.ctx.setLineDash([7, 6])
        const w = K.measure(L(key), 22, 500, 'mono') + 28
        K.strokeRR(x, 922, w, 42, 8, C.bg, 2)
        K.ctx.restore()
        K.text(L(key), x + 14, 951, { size: 22, weight: 500, fam: 'mono', color: C.bg })
        x += w + 16
      }
      K.cite(L('cite1'), 1, C.inkMute)
    })
  })
}
