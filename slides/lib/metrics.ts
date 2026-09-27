/**
 * Every number the deck shows comes from data/metrics.yml, never from a scene.
 *
 *   data.rows_ingested:
 *     value: 23471159
 *     display: 23.5M
 *     kind: offline            offline | provisional | projection | simulation | synthetic
 *     source: docs/data/quality-report.md
 *
 *   eval.safe_resolution:
 *     status: pending          renders visibly as pending until phase 14 lands
 *     kind: offline
 *     source: docs/evaluation/ (phase 14)
 *
 * The brief requires offline measurements, simulations and projections to be
 * labeled separately, so `kind` is mandatory and scenes print it next to the
 * number. `pnpm check:content` lists pending metrics; `--strict` fails on any.
 */
import { parse } from 'yaml'
import raw from '../data/metrics.yml?raw'

import type { MetricKind } from './metric-kinds'
export type { MetricKind } from './metric-kinds'
export { KIND_LABEL } from './metric-kinds'

export interface MetricEntry {
  value?: number | string
  display?: string
  status?: 'ok' | 'pending'
  kind: MetricKind
  source: string
  note?: string
}

export interface Metric {
  key: string
  /** the string to draw: `display`, else the value, else "pending" */
  text: string
  /** numeric value for counters and bars; NaN when pending or non-numeric */
  num: number
  pending: boolean
  kind: MetricKind
  source: string
}

export const metrics: Record<string, MetricEntry> = (parse(raw) ?? {}) as Record<string, MetricEntry>

export const isPending = (e: MetricEntry | undefined) =>
  !e || e.status === 'pending' || e.value === undefined || e.value === null

export function metric(key: string): Metric {
  const e = metrics[key]
  const pending = isPending(e)
  const num = !pending && typeof e?.value === 'number' ? e.value : Number.NaN
  return {
    key,
    text: pending ? 'pending' : (e?.display ?? String(e?.value)),
    num,
    pending,
    kind: e?.kind ?? 'offline',
    source: e?.source ?? `[missing metric ${key}]`,
  }
}
