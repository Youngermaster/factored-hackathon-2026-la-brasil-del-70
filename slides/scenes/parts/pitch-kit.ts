/**
 * Shared pieces of the six static pitch slides (pitch.md, scenes/pitch*.ts).
 *
 * The video deck (slides.md) replaces its content between clicks, so no single
 * frame carries a whole slide. The pitch scenes compose those final states
 * into one still frame each: one cue, nothing animated, every element drawn at
 * rest. They reuse the deck's kit, colours, metrics and strings, so a number
 * or a word changed in data/metrics.yml or locales/en.yml changes both decks.
 */
import type { Kit } from '../../lib/scene/kit'
import { C, MX, W } from '../../lib/scene/kit'
import { labeler } from '../../lib/scene/strings'

/** Strings of the video deck's scenes, so the pitch reuses their exact wording. */
export const S = {
  hook: labeler('hook'),
  thesis: labeler('thesis'),
  arch: labeler('arch'),
  workflows: labeler('workflows'),
  evidence: labeler('evidence'),
  close: labeler('close'),
}

export type PBoxKind = 'ink' | 'blue' | 'yellow' | 'dashed' | 'paper'

const COLORS: Record<PBoxKind, { fill?: string; fg: string; sub: string; stroke?: string }> = {
  ink: { fill: C.bg, fg: C.paper, sub: C.dim },
  blue: { fill: C.blue, fg: C.bg, sub: C.bg },
  yellow: { fill: C.yellow, fg: C.bg, sub: C.inkDim },
  dashed: { fg: C.bg, sub: C.inkDim, stroke: C.bg },
  paper: { fill: C.paper, fg: C.bg, sub: C.inkDim },
}

/**
 * A compact labelled box at rest: a label and any number of mono sub-lines,
 * centred vertically. Returns its geometry for connectors.
 */
export function pbox(
  K: Kit, kind: PBoxKind, x: number, y: number, w: number, h: number,
  label: string, subs: readonly string[] = [], o: { size?: number; sub?: number; pad?: number } = {},
) {
  const size = o.size ?? 24
  const sub = o.sub ?? 20
  const pad = o.pad ?? 18
  const c = COLORS[kind]
  if (c.fill) K.fillRR(x, y, w, h, 10, c.fill)
  if (c.stroke) {
    K.ctx.save()
    K.ctx.setLineDash([9, 7])
    K.strokeRR(x, y, w, h, 10, c.stroke, 2)
    K.ctx.restore()
  }
  const lh = sub * 1.3
  const block = size + subs.length * lh
  let by = y + (h - block) / 2 + size * 0.8
  K.text(label, x + pad, by, { size, weight: 700, color: c.fg })
  for (const s of subs) {
    by += lh
    K.text(s, x + pad, by + 2, { size: sub, weight: 500, fam: 'mono', color: c.sub })
  }
  return { x, y, w, h, cx: x + w / 2, cy: y + h / 2, r: x + w, b: y + h }
}

/** The citation line, shrunk until it fits the content width. */
export function citeFit(K: Kit, s: string, color: string = C.mute, y = 1032) {
  let size = 22
  while (size > 16 && K.measure(s, size, 400, 'mono') > W - 2 * MX) size -= 1
  K.text(s, MX, y, { size, weight: 400, fam: 'mono', color })
}

/** A static slide title, top-left, in the deck's title voice. */
export function ptitle(K: Kit, s: string, color: string = C.paper, size = 56) {
  K.words(s, MX, 150, { t: 30, t0: 0, size, weight: 700, fam: 'display', maxW: 1500, lh: 1.1, color })
}
