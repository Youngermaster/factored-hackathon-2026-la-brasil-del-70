import type { Kit } from './kit'
import type { Metric } from '../metrics'

export interface SceneEnv {
  /** playhead, seconds */
  t: number
  /** the click the slide is on (0 = just arrived) */
  stage: number
  /** this scene's strings from locales/en.yml: L('title') */
  L: (key: string) => string
  /** a number from data/metrics.yml, with its kind, source and pending state */
  M: (key: string) => Metric
  K: Kit
  ctx: CanvasRenderingContext2D
}

export interface SceneDef {
  /**
   * Where the playhead RESTS at each click: cues[0] is the end of the arrival
   * animation, cues[k] the end of click k. The slide's `clicks:` frontmatter
   * must equal cues.length - 1 (pnpm check:content enforces it).
   * Between cues the scene plays in real time; nothing moves once it lands.
   */
  cues: readonly number[]
  draw: (env: SceneEnv) => void
}

export const defineScene = (d: SceneDef): SceneDef => d
