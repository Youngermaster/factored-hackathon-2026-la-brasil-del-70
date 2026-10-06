/**
 * Pitch slide 6 (static): how it fails, what we cannot claim, and the thesis.
 *
 *   left    the degradation ladder L0 to L4, each level with the failure that
 *           pushes the service down to it; writes never fail open
 *   right   the limits we state, and the next steps
 *   bottom  defense in depth on one host, the thesis, the repository and the
 *           deployed URL
 */
import { defineScene } from '../lib/scene/types'
import { C, MX } from '../lib/scene/kit'
import { metrics } from '../lib/metrics'
import { check, cross, dims, tab } from '../lib/scene/bank'
import { S, citeFit, ptitle } from './parts/pitch-kit'

const RX = 1080

export default defineScene({
  cues: [30],
  draw({ L, M, K }) {
    const CL = S.close
    dims(K, CL('dims'))
    ptitle(K, CL('ladderTitle'))

    // ── the degradation ladder ────────────────────────────────────────────
    for (let i = 0; i < 5; i++) {
      const y = 262 + i * 72
      const x = MX + i * 40
      const last = i === 4
      K.fillRR(x, y - 30, 360, 6, 3, last ? C.red : i === 0 ? C.yellow : C.dim)
      K.chip(`L${i}`, x, y - 12, { bg: last ? C.red : C.bg2, fg: last ? C.bg : C.paper, size: 22, weight: 700 })
      K.text(CL(`lv${i}`), x + 70, y + 16, { size: 26, weight: 500 })
      if (i > 0) K.label(CL(`why${i}`), 640, y + 14, { size: 20, color: C.redText })
      if (last) cross(K, 940, y + 6, 22, 1, C.red, 5)
      else check(K, 940, y + 6, 24, 1, C.yellow, 5)
    }
    K.label(L('lanes'), 640, 236, { size: 20 })
    K.words(CL('ladderPunch'), MX, 656, { t: 30, t0: 0, size: 32, weight: 600, fam: 'sans', ls: -0.01, accent: C.yellow, maxW: 860 })

    // ── the limits we state, and what comes next ──────────────────────────
    K.line(RX - 40, 220, RX - 40, 720, C.faint, 2)
    K.text(CL('limitsTitle'), RX, 250, { size: 30, weight: 700, fam: 'display' })
    ;(['l0', 'l1', 'l2', 'l3'] as const).forEach((k, i) => {
      const y = 300 + i * 66
      K.fillRR(RX, y - 20, 6, 52, 3, C.red)
      K.text(CL(k), RX + 24, y, { size: 26, weight: 600 })
      K.label(CL(`${k}s`), RX + 24, y + 30, { size: 20, color: C.dim })
    })
    K.label(CL('nextLbl'), RX, 586, { size: 22, color: C.yellow, weight: 600 })
    let nx = RX
    let ny = 602
    ;(['n0', 'n1', 'n2', 'n3'] as const).forEach((k) => {
      const w = K.measure(CL(k), 20, 500, 'mono') + 32
      if (nx + w > 1800) {
        nx = RX
        ny += 46
      }
      K.chip(CL(k), nx, ny, { bg: C.bg2, fg: C.paper, size: 20 })
      nx += w + 12
    })

    // ── defense in depth, the thesis, the links ───────────────────────────
    K.line(MX, 750, 1800, 750, C.faint, 2)
    K.label(L('defense'), MX, 802, { size: 22, color: C.dim })
    let gx = MX + K.measure(L('defense'), 22, 500, 'mono') + 20
    for (let i = 0; i < 8; i++) gx += tab(K, CL(`g${i}`), gx, 776, { tone: i === 6 ? 'yellow' : 'paper', size: 20 }) + 10
    K.words(`${CL('c1')} ${CL('c2')} ${CL('c3')}`, MX, 892, { t: 30, t0: 0, size: 38, weight: 700, fam: 'display', accent: C.yellow, maxW: 1700, ls: -0.02 })
    const url = String(metrics['deploy.url']?.value ?? M('deploy.url').text)
    K.label(`${L('repoLbl')}  ${CL('repo')}`, MX, 950, { size: 22, color: C.paper })
    K.label(`${CL('deployed')}  ${url}`, MX, 984, { size: 22, color: C.yellow })
    citeFit(K, L('cite'))
  },
})
