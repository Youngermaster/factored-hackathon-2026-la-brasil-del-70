/**
 * Defense in depth on the close scene (scenes/close.ts), phase 16: one
 * request lane from the browser to PostgreSQL through every control. A
 * legitimate request passes them all; each attack (red) stops at the layer
 * built for it; retention purges old conversation text inside the database.
 * Controls follow docs/security/threat-model.md; the host is one VM with
 * Docker Compose behind Caddy (ADR 0019), and its URL stays pending.
 */
import type { SceneEnv } from '../../lib/scene/types'
import { C, MX } from '../../lib/scene/kit'
import { outCubic, outExpo, presence, seg } from '../../lib/scene/math'
import { cross, metricValue } from '../../lib/scene/bank'
import { packet, ring } from '../../lib/scene/fx'

const LANE = 560
const GATES = 7
const GX = (i: number) => 400 + i * 195
const DBX = 1720

export function defense({ t, L, M, K }: SceneEnv, c1: number, tout: number) {
  K.fade(presence(t, c1, tout, 0.3, 0.25), () => {
    // the two ends: the browser (data in) and the database
    K.fade(outCubic(seg(t, c1 + 0.1, c1 + 0.4)), () => {
      K.fillRR(MX, LANE - 50, 190, 100, 12, C.bg2)
      K.text(L('browser'), MX + 95, LANE + 9, { size: 28, weight: 600, align: 'center' })
      K.fillRR(DBX - 60, LANE - 70, 180, 140, 12, C.paper)
      K.text(L('db'), DBX + 30, LANE + 9, { size: 26, weight: 700, color: C.bg, align: 'center' })
    })
    const lk = outExpo(seg(t, c1 + 0.2, c1 + 0.8))
    if (lk > 0) K.line(MX + 190, LANE, MX + 190 + (DBX - 60 - MX - 190) * lk, LANE, C.faint, 4)
    // the gates: deterministic controls, so yellow; labels alternate above and below
    for (let i = 0; i < GATES; i++) {
      const k = seg(t, c1 + 0.3 + i * 0.07, c1 + 0.7 + i * 0.07)
      if (k > 0) K.fillRR(GX(i) - 7, LANE - 80 * outExpo(k), 14, 160 * outExpo(k), 7, C.yellow)
      const up = i % 2 === 0
      K.fade(outCubic(seg(t, c1 + 0.5 + i * 0.07, c1 + 0.8 + i * 0.07)), () =>
        K.text(L(`g${i}`), GX(i), up ? LANE - 104 : LANE + 128, { size: 24, weight: 500, fam: 'mono', color: C.yellow, align: 'center' }))
    }
    // a legitimate request crosses every gate and reaches its own rows
    const lane = [{ x: MX + 190, y: LANE }, { x: DBX - 60, y: LANE }]
    packet(K, lane, seg(t, c1 + 1.0, c1 + 2.0), C.paper, 11)
    // attacks: each one stops at the gate built for it (TLS, CSP, cookies, CSRF, roles, rate limits, RLS)
    for (let i = 0; i < 7; i++) {
      const t0 = c1 + 1.4 + i * 0.22
      const y = LANE + (i % 2 ? 26 : -26)
      packet(K, [{ x: MX + 190, y }, { x: GX(i) - 12, y }], seg(t, t0, t0 + 0.5), C.red, 8)
      ring(K, GX(i), y, seg(t, t0 + 0.5, t0 + 1.0), C.red, 8, 50)
      cross(K, GX(i) - 30, y, 16, seg(t, t0 + 0.5, t0 + 0.7), C.red, 4)
    }
    // retention: old conversation text fades out of the database
    for (let j = 0; j < 3; j++) {
      const a = 1 - outCubic(seg(t, c1 + 2.8 + j * 0.15, c1 + 3.2 + j * 0.15))
      K.fade(outCubic(seg(t, c1 + 0.4, c1 + 0.7)) * a, () => K.fillRR(DBX - 34 + j * 44, LANE + 34, 30, 10, 5, C.inkMute))
    }
    K.fade(outCubic(seg(t, c1 + 2.9, c1 + 3.2)), () =>
      K.text(L('g7'), DBX + 30, LANE + 128, { size: 24, weight: 500, fam: 'mono', color: C.yellow, align: 'center' }))
    // the host, and the deployed URL, which stays pending until the human deploys
    K.fade(outCubic(seg(t, c1 + 2.4, c1 + 2.8)), () => {
      K.text(L('host'), MX, 860, { size: 30, weight: 600 })
      K.label(L('deployed'), MX, 930, { size: 24 })
      metricValue(K, M('deploy.url'), MX + 200, 940, { size: 40, fam: 'mono' })
    })
  })
}
