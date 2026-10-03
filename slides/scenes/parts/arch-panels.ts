/**
 * The right-hand panels of the architecture scene (scenes/arch.ts), one per
 * click, each a small mechanism instead of a paragraph. Drawn on the
 * light-gray ground: ink text, accents as fills with ink text on top.
 */
import type { SceneEnv } from '../../lib/scene/types'
import { C } from '../../lib/scene/kit'
import { clamp, hash, outCubic, presence, seg } from '../../lib/scene/math'
import { check, cross, tab } from '../../lib/scene/bank'
import { glyph, packet } from '../../lib/scene/fx'

const PX = 1340

export function panels({ t, L, M, K }: SceneEnv) {
  const head = (key: string, bar: string, t0: number) => {
    K.fade(outCubic(seg(t, t0, t0 + 0.3)), () => K.fillRR(PX, 290, 44, 8, 4, bar))
    K.words(L(key), PX, 350, { t, t0, size: 40, weight: 700, fam: 'display', color: C.bg, stagger: 0.03 })
  }
  const note = (s: string, y: number, t0: number) =>
    K.fade(outCubic(seg(t, t0, t0 + 0.4)), () =>
      K.wrap(s, 460, 28, 500).forEach((ln, i) => K.text(ln, PX, y + i * 38, { size: 28, weight: 500, color: C.inkDim })))
  const inkChip = (s: string, x: number, y: number, k: number, size = 24) =>
    K.chip(s, x, y, { bg: C.bg, fg: C.paper, k, size, weight: 600 })

  // 1 policy kernel: clause file, rule call, Decision
  K.fade(presence(t, 2.5, 5.25, 0.3, 0.25), () => {
    head('p1h', C.yellow, 2.6)
    glyph(K, 'clause', PX + 22, 432, 40, C.bg, seg(t, 2.8, 3.2))
    K.fade(outCubic(seg(t, 2.9, 3.2)), () => K.text(L('p1file'), PX + 60, 442, { size: 24, weight: 500, fam: 'mono', color: C.bg }))
    const chain = [{ x: PX + 22, y: 462 }, { x: PX + 22, y: 520 }]
    packet(K, chain, seg(t, 3.1, 3.5), C.bg, 8)
    inkChip(L('p1rule'), PX, 522, seg(t, 3.3, 3.7))
    packet(K, [{ x: PX + 22, y: 566 }, { x: PX + 22, y: 616 }], seg(t, 3.6, 4.0), C.bg, 8)
    tab(K, L('p1dec'), PX, 618, { tone: 'yellow', k: seg(t, 3.8, 4.2), size: 24 })
    note(L('p1c'), 740, 4.3)
  })

  // 2 LLM gateway: a request falls through the eight decorators
  K.fade(presence(t, 5.3, 8.45, 0.3, 0.25), () => {
    head('p2h', C.blue, 5.5)
    for (let i = 0; i < 8; i++) {
      const k = outCubic(seg(t, 5.8 + i * 0.07, 6.2 + i * 0.07))
      K.fade(k, () => {
        K.fillRR(PX + i * 12, 400 + i * 42, 440 - i * 24, 34, 6, C.blue)
        K.text(L(`d${i + 1}`), PX + i * 12 + 16, 424 + i * 42, { size: 22, weight: 600, fam: 'mono', color: C.bg })
      })
    }
    // the call lands on the provider the settings name: local Ollama today, a hosted model by configuration
    packet(K, [{ x: PX + 420, y: 390 }, { x: PX + 420 - 7 * 12, y: 744 }, { x: PX + 110, y: 790 }], seg(t, 6.5, 7.4), C.bg, 9)
    K.fade(outCubic(seg(t, 6.9, 7.2)), () => {
      K.fillRR(PX, 756, 220, 84, 10, C.blue)
      K.text(L('prov1'), PX + 20, 792, { size: 26, weight: 700, color: C.bg })
      K.text(L('prov1s'), PX + 20, 824, { size: 22, weight: 500, fam: 'mono', color: C.bg })
    })
    K.fade(outCubic(seg(t, 7.2, 7.5)), () => {
      K.ctx.save()
      K.ctx.setLineDash([8, 7])
      K.strokeRR(PX + 240, 756, 220, 84, 10, C.bg, 2)
      K.ctx.restore()
      K.text(L('prov2'), PX + 260, 792, { size: 26, weight: 600, color: C.bg })
      K.text(L('prov2s'), PX + 260, 824, { size: 22, weight: 500, fam: 'mono', color: C.inkDim })
    })
    note(L('p2c'), 900, 7.6)
  })

  // 3 grounding verifier: one draft passes, one is replaced by the template
  K.fade(presence(t, 8.5, 11.45, 0.3, 0.25), () => {
    head('p3h', C.yellow, 8.7)
    const row = (draft: string, y: number, t0: number, ok: boolean) => {
      const slide = outCubic(seg(t, t0, t0 + 0.5))
      const w = tab(K, draft, PX - 40 * (1 - slide), y, { tone: 'blue', k: seg(t, t0, t0 + 0.3), size: 24 })
      K.arrow(PX + w + 8, y + 20, PX + w + 44, y + 20, { color: C.bg, k: outCubic(seg(t, t0 + 0.4, t0 + 0.6)), head: 10 })
      const gx = PX + w + 52
      const gw = tab(K, L('gate'), gx, y, { tone: 'yellow', k: seg(t, t0 + 0.5, t0 + 0.8), size: 24 })
      if (ok) {
        check(K, gx + gw + 30, y + 20, 28, seg(t, t0 + 0.8, t0 + 1.1), C.bg, 5)
        K.fade(outCubic(seg(t, t0 + 0.9, t0 + 1.2)), () => K.text(L('send'), gx + gw + 60, y + 30, { size: 28, weight: 600, color: C.bg }))
      }
      else {
        cross(K, gx + gw + 30, y + 20, 26, seg(t, t0 + 0.8, t0 + 1.1), C.red, 6)
        tab(K, L('template'), gx, y + 70, { tone: 'yellow', k: seg(t, t0 + 1.1, t0 + 1.5), size: 24 })
      }
    }
    row(L('draftOk'), 420, 9.0, true)
    row(L('draftBad'), 560, 9.7, false)
    note(L('p3c'), 780, 10.9)
  })

  // 4 data platform: rows flow raw to gold, bad rows drop into quarantine
  K.fade(presence(t, 11.5, 14.25, 0.3, 0.25), () => {
    head('p4h', C.bg, 11.7)
    const xs: number[] = []
    let x = PX
    for (let i = 1; i <= 4; i++) {
      xs.push(x)
      x += inkChip(L(`s${i}`), x, 410, seg(t, 11.9 + i * 0.1, 12.3 + i * 0.1), 22) + 26
    }
    const lane = [{ x: PX, y: 470 }, { x: x - 26, y: 470 }]
    for (let j = 0; j < 7; j++) {
      const t0 = 12.4 + j * 0.12
      if (j === 3) packet(K, [{ x: PX, y: 470 }, { x: xs[1] + 40, y: 470 }, { x: xs[1] + 40, y: 540 }], seg(t, t0, t0 + 0.6), C.red, 8)
      else packet(K, lane, seg(t, t0, t0 + 0.8 + hash(j) * 0.2), C.bg, 7)
    }
    K.fade(outCubic(seg(t, 12.7, 13.0)), () => {
      K.chip(L('quarantine'), xs[1], 548, { bg: C.red, fg: C.bg, size: 24, weight: 700 })
      K.text(M('data.rows_ingested').text, PX, 690, { size: 52, weight: 800, fam: 'display', color: C.bg })
      K.label(L('rowsIn'), PX, 728, { size: 22, color: C.inkMute })
      K.text(M('data.rows_quarantined').text, PX, 820, { size: 52, weight: 800, fam: 'display', color: C.bg })
      K.label(L('rowsQ'), PX, 858, { size: 22, color: C.inkMute })
    })
  })

  // 5 direction: the ports the core owns
  K.fade(outCubic(seg(t, 14.3, 14.6)), () => {
    head('p5h', C.bg, 14.4)
    for (let i = 0; i < 6; i++) {
      const k = seg(t, 14.9 + i * 0.1, 15.3 + i * 0.1)
      K.chip(L(`port${i + 1}`), PX + (i % 2) * 272, 420 + Math.floor(i / 2) * 64, { bg: C.bg, fg: C.paper, k, size: 22, weight: 600 })
    }
    note(L('p5c'), 680, 15.8)
    void clamp
  })
}
