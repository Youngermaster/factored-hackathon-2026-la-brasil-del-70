/**
 * Pitch slide 3 (static): the full architecture on one frame.
 *
 *   top     the cloud: GitHub Actions (ci, the deploy workflow over OpenID
 *           Connect, GHCR images by digest, smoke test with automatic
 *           rollback), one Azure VM running Docker Compose (Caddy with the
 *           React SPA, the FastAPI api, PostgreSQL 16 with row-level security,
 *           Qdrant, the one-shot jobs, the obs profile), Azure OpenAI through
 *           LiteLLM, and Key Vault read by the VM's managed identity
 *   bottom  inside the api: one turn through the hexagonal core, the learned
 *           components against their baselines, and the data platform
 *
 * Facts: deploy/compose.prod.yml, deploy/README.md, docs/architecture,
 * ADR 0019, 0037, 0038, 0047, docs/models, docs/evaluation/results.md.
 */
import { defineScene } from '../lib/scene/types'
import { C, MX } from '../lib/scene/kit'
import { dims } from '../lib/scene/bank'
import { ground } from '../lib/scene/fx'
import { region, wire } from './parts/arch-kit'
import { citeFit, pbox, ptitle } from './parts/pitch-kit'

const VM = { x: 450, y: 222, w: 1010, h: 392 }

export default defineScene({
  cues: [30],
  draw({ L, M, K }) {
    ground(K, C.paper)
    dims(K, L('dims'), 1, C.inkMute)
    ptitle(K, L('title'), C.bg)

    // ── the cloud: GitHub on the left ─────────────────────────────────────
    const gx = MX
    const gw = 292
    const gh = 72
    const gys = [228, 322, 416, 510]
    const gh1 = pbox(K, 'ink', gx, gys[0], gw, gh, L('gh'), [L('ghS')])
    const ghcr = pbox(K, 'ink', gx, gys[1], gw, gh, L('ghcr'), [L('ghcrS')])
    const dep = pbox(K, 'ink', gx, gys[2], gw, gh, L('deploy'), [L('deployS')])
    const smoke = pbox(K, 'dashed', gx, gys[3], gw, gh, L('smoke'), [L('smokeS')])
    for (const [a, b] of [[gh1, ghcr], [ghcr, dep], [dep, smoke]] as const) wire(K, [{ x: a.cx, y: a.b }, { x: b.cx, y: b.y }], 1, C.bg, 2)

    // ── the VM ────────────────────────────────────────────────────────────
    region(K, VM.x, VM.y, VM.w, VM.h, '', 1, false)
    K.text(L('vm'), VM.x + VM.w - 24, VM.y + VM.h - 20, { size: 22, weight: 600, fam: 'mono', color: C.inkDim, align: 'right' })
    wire(K, [{ x: ghcr.r, y: ghcr.cy }, { x: VM.x, y: ghcr.cy }], 1, C.bg, 2)
    wire(K, [{ x: dep.r, y: dep.cy }, { x: VM.x, y: dep.cy }], 1, C.bg, 2)
    K.text(L('browser'), 480, 208, { size: 22, weight: 500, fam: 'mono', color: C.inkDim })

    const web = pbox(K, 'ink', 480, 250, 300, 84, L('web'), [L('webS')])
    K.arrow(560, 216, 560, web.y, { color: C.bg, lw: 2, head: 12 })
    const api = pbox(K, 'yellow', 820, 250, 260, 84, L('api'), [L('apiS')])
    const pg = pbox(K, 'ink', 1120, 250, 310, 84, L('pg'), [L('pgS')])
    wire(K, [{ x: web.r, y: web.cy }, { x: api.x, y: api.cy }], 1, C.bg, 2)
    wire(K, [{ x: api.r, y: api.cy }, { x: pg.x, y: pg.cy }], 1, C.bg, 2)
    const qd = pbox(K, 'ink', 880, 356, 200, 72, L('qdrant'), [L('qdrantS')])
    wire(K, [{ x: 1000, y: api.b }, { x: 1000, y: qd.y }], 1, C.bg, 2)
    K.chip(L('jobs'), 1120, 362, { bg: C.bg, fg: C.paper, size: 20, weight: 600 })

    // the obs profile
    region(K, 480, 448, 950, 116, '', 1, true)
    K.text(L('obs'), 496, 488, { size: 22, weight: 600, fam: 'mono', color: C.inkDim })
    K.text(L('obsS'), 496, 516, { size: 20, weight: 500, fam: 'mono', color: C.inkMute })
    const ow = 176
    const obs = (['col', 'prom', 'graf', 'jae'] as const).map((k, i) =>
      pbox(K, 'ink', 664 + i * (ow + 12), 462, ow, 86, L(k), [L(`${k}S`)], { pad: 16 }))
    wire(K, [{ x: 840, y: api.b }, { x: 840, y: 440 }, { x: obs[0].cx, y: 440 }, { x: obs[0].cx, y: obs[0].y }], 1, C.bg, 2)

    // ── the managed services on the right ─────────────────────────────────
    const aoai = pbox(K, 'blue', 1500, 230, 300, 132, L('aoai'), [L('aoaiS1'), L('aoaiS2'), L('aoaiS3')])
    wire(K, [{ x: 1000, y: api.y }, { x: 1000, y: 238 }, { x: aoai.x, y: 238 }], 1, C.blue, 2)
    const kv = pbox(K, 'ink', 1500, 384, 300, 84, L('kv'), [L('kvS')])
    wire(K, [{ x: kv.x, y: kv.cy }, { x: VM.x + VM.w, y: kv.cy }], 1, C.bg, 2)
    K.text(L('kvNote'), 1500, 500, { size: 20, weight: 500, fam: 'mono', color: C.inkDim })
    K.text(L('kvNote2'), 1500, 528, { size: 20, weight: 500, fam: 'mono', color: C.inkDim })

    // ── inside the api: one turn through the hexagonal core ───────────────
    K.line(MX, 640, 1800, 640, C.inkMute, 1)
    K.text(L('inside'), MX, 676, { size: 22, weight: 600, fam: 'mono', color: C.inkDim })
    K.text(L('layers'), 1800, 676, { size: 20, weight: 500, fam: 'mono', color: C.inkDim, align: 'right' })
    const turn = [
      ['blue', 'tRouter', 'tRouterS'],
      ['yellow', 'tState', 'tStateS'],
      ['yellow', 'tPolicy', 'tPolicyS'],
      ['yellow', 'tTools', 'tToolsS'],
      ['yellow', 'tGround', 'tGroundS'],
      ['ink', 'tRecord', 'tRecordS'],
    ] as const
    const tw = 256
    const tg = (1680 - 6 * tw) / 5
    turn.forEach(([kind, a, b], i) => {
      const x = MX + i * (tw + tg)
      pbox(K, kind, x, 696, tw, 84, L(a), [L(b)])
      if (i < 5) wire(K, [{ x: x + tw + 2, y: 738 }, { x: x + tw + tg - 2, y: 738 }], 1, C.bg, 2)
    })

    // learned components behind ports, against their served baselines
    K.text(L('learned'), MX, 832, { size: 20, weight: 600, fam: 'mono', color: C.inkDim })
    const cells = [
      ['cRouter', 'ml.router.f1.keyword', 'ml.router.f1.embeddings', 'cRouterB', 'cRouterL'],
      ['cRes', 'ml.resolver.coverage.rules', 'ml.resolver.coverage.lgbm', 'cResB', 'cResL'],
      ['cRisk', 'ml.risk.auc.score_band', 'ml.risk.auc.logreg', 'cRiskB', 'cRiskL'],
      ['cE2e', 'ml.e2e.dev.baselines', 'ml.e2e.dev.learned', 'cE2eB', 'cE2eL'],
    ] as const
    cells.forEach(([lbl, kb, kl, lb, ll], i) => {
      const x = MX + i * 266
      pbox(K, 'dashed', x, 850, 250, 112, L(lbl), [`${L(lb)}  ${M(kb).text}`, `${L(ll)}  ${M(kl).text}`], { pad: 16 })
    })

    // the data platform feeds the seed and the evaluation
    const dp = pbox(K, 'ink', 1220, 850, 300, 112, L('data'), [L('dataS'), L('dataS2')])
    const seed = K.chip(L('seed'), 1580, 856, { bg: C.bg, fg: C.paper, size: 20, weight: 600 })
    K.chip(L('evalH'), 1580, 914, { bg: C.bg, fg: C.paper, size: 20, weight: 600 })
    wire(K, [{ x: dp.r, y: 873 }, { x: 1578, y: 873 }], 1, C.bg, 2)
    wire(K, [{ x: dp.r, y: 931 }, { x: 1578, y: 931 }], 1, C.bg, 2)
    void seed

    citeFit(K, L('cite'), C.inkMute)
  },
})
