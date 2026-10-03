/**
 * Slide 5, evidence: the phase 14b test run, P against B0 and B1 on the same
 * 304 held-out workflow cases, simulated on a local open model.
 *
 *   arrive  the 304 cases (gray, data) stream into the three systems
 *   1       safe automated resolution per workflow first: intervals grow out
 *           of each point estimate; card support is flagged, B0 is ahead
 *   2       the rows fold into the aggregate, then the trade-offs: missed and
 *           unnecessary transfers, latency
 *   3       unsafe outcomes: the same cases turn red one by one, and B1's 90
 *           stream into what they did
 *   4       where P is weak: the echoed merchant name, the distress transfers
 *
 * The system tabs travel with the story: rows, then column headers, then the
 * labels of the three grids. Every number reads data/metrics.yml.
 */
import { defineScene } from '../lib/scene/types'
import { C, MX } from '../lib/scene/kit'
import { inOutCubic, lerp, outCubic, presence, seg } from '../lib/scene/math'
import { KIND_LABEL } from '../lib/metrics'
import { packet } from '../lib/scene/fx'
import { COLX, SYS, rates, sysTab } from './parts/evidence-rates'
import { GX, grid, unsafe, weak } from './parts/evidence-unsafe'

const CUES = [2.8, 6.4, 10.0, 14.2, 18.0] as const
const TITLES = ['t0', 't1', 't2', 't3', 't4'] as const

export default defineScene({
  cues: CUES,
  draw(env) {
    const { t, L, M, K } = env
    const c = [0, CUES[0] + 0.05, CUES[1] + 0.05, CUES[2] + 0.05, CUES[3] + 0.05]
    TITLES.forEach((key, i) => K.title(L(key), t, i ? c[i] + 0.1 : 0.1, { tout: i < 4 ? c[i + 1] : undefined }))
    const m = M('eval.sar.all.p')
    K.fade(outCubic(seg(t, 1.6, 2.0)), () => K.cite(`${KIND_LABEL[m.kind]} ${L('onModel')}  |  ${m.source}  |  ${L('run')}`))

    // ── arrive: the 304 cases stream into the three systems ───────────────
    K.fade(presence(t, 0.2, c[1], 0.3, 0.25), () => {
      grid(K, 0, seg(t, 0.3, 1.2), () => 0)
      K.fade(outCubic(seg(t, 0.9, 1.3)), () => {
        K.text(M('eval.cases').text, MX, 700, { size: 64, weight: 800, fam: 'display' })
        K.text(L('casesLbl'), MX, 748, { size: 28, weight: 500 })
        K.label(L('casesSub'), MX, 790, { size: 22 })
      })
      SYS.forEach((_, i) => {
        for (let j = 0; j < 3; j++) packet(K, [{ x: 470, y: 480 + (j - 1) * 60 }, { x: 990, y: 382 + i * 130 }], seg(t, 1.1 + i * 0.12 + j * 0.1, 1.7 + i * 0.12 + j * 0.1), C.dim, 7)
        K.fade(outCubic(seg(t, 1.5 + i * 0.12, 1.9 + i * 0.12)), () => {
          K.text(L(`name${i}`), 1110, 394 + i * 130, { size: 34, weight: 600 })
          K.label(L(`model${i}`), 1110, 432 + i * 130, { size: 22 })
        })
      })
    })

    // ── the system tabs: rows, then column headers, then grid labels ─────
    const toHead = inOutCubic(seg(t, c[1], c[1] + 0.6))
    const toGrid = inOutCubic(seg(t, c[3], c[3] + 0.6))
    K.fade(presence(t, 1.3, c[4], 0.3, 0.25), () => {
      SYS.forEach((_, i) => {
        const x = lerp(lerp(1040, COLX[i], toHead), GX[i] + 30, toGrid)
        const y = lerp(lerp(362 + i * 130, 262, toHead), 282, toGrid)
        sysTab(K, L, i, x, y, seg(t, 1.3 + i * 0.12, 1.7 + i * 0.12), 26)
      })
    })

    rates(env, c[1], c[2], c[3])
    unsafe(env, c[3], c[4])
    weak(env, c[4])
  },
})
