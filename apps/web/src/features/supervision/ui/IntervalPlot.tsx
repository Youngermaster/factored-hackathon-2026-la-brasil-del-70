import { useId } from 'react';
import { useTranslation } from 'react-i18next';

import { cx } from '@/shared/lib/cx';

import { position } from '../model/evidence';
import { useEvidenceFormat } from './format';

export interface PlotPoint {
  readonly label: string;
  readonly value: number;
  readonly low: number | null;
  readonly high: number | null;
  /** Rule-based baselines are drawn in the decision tone, trained models in the understanding tone. */
  readonly tone: 'decision' | 'understanding';
  readonly serving: boolean;
}

const TICKS = [0, 0.25, 0.5, 0.75, 1] as const;

/**
 * A dot-and-whisker plot of one ratio metric on a fixed 0 to 1 axis, one row per model. The plot is an image whose
 * accessible name states every value and interval; the table next to it carries the same numbers.
 */
export function IntervalPlot({
  metric,
  points,
}: {
  readonly metric: string;
  readonly points: readonly PlotPoint[];
}) {
  const { t } = useTranslation();
  const format = useEvidenceFormat();
  const titleId = useId();
  const descriptionId = useId();
  const description = points
    .map((point) =>
      point.low === null || point.high === null
        ? t('supervision.offline.plotPoint', {
            model: point.label,
            value: format.decimal(point.value),
          })
        : t('supervision.offline.plotPointInterval', {
            model: point.label,
            value: format.decimal(point.value),
            low: format.decimal(point.low),
            high: format.decimal(point.high),
          }),
    )
    .join('; ');
  return (
    <figure className="flex flex-col gap-2">
      <figcaption id={titleId} className="text-caption font-medium text-fg-secondary">
        {t('supervision.offline.plotTitle', { metric })}
      </figcaption>
      <p id={descriptionId} className="sr-only">
        {description}
      </p>
      <div
        role="img"
        aria-labelledby={titleId}
        aria-describedby={descriptionId}
        className="flex flex-col gap-2"
      >
        {points.map((point) => (
          <div
            key={point.label}
            className="grid grid-cols-[minmax(0,11rem)_minmax(0,1fr)] items-center gap-3"
          >
            <span
              className={cx(
                'truncate font-mono text-caption',
                point.serving ? 'font-semibold text-fg' : 'text-fg-secondary',
              )}
              title={point.label}
            >
              {point.label}
            </span>
            <div className="relative h-5 rounded-control bg-surface-sunken" aria-hidden="true">
              {TICKS.slice(1, -1).map((tick) => (
                <span
                  key={tick}
                  className="absolute inset-y-0 w-px bg-border"
                  style={{ left: `${String(position(tick, 1))}%` }}
                />
              ))}
              {point.low !== null && point.high !== null && (
                <span
                  className={cx(
                    'absolute top-1/2 h-0.5 -translate-y-1/2',
                    point.tone === 'understanding' ? 'bg-understanding-text' : 'bg-fg',
                  )}
                  style={{
                    left: `${String(position(point.low, 1))}%`,
                    width: `${String(Math.max(position(point.high, 1) - position(point.low, 1), 0.5))}%`,
                  }}
                />
              )}
              <span
                className={cx(
                  'absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2',
                  point.tone === 'understanding'
                    ? 'border-understanding-text bg-understanding'
                    : 'border-fg bg-decision',
                )}
                style={{ left: `${String(position(point.value, 1))}%` }}
              />
            </div>
          </div>
        ))}
        <div className="grid grid-cols-[minmax(0,11rem)_minmax(0,1fr)] gap-3" aria-hidden="true">
          <span />
          <div className="relative h-4">
            {TICKS.map((tick) => (
              <span
                key={tick}
                className="absolute -translate-x-1/2 font-mono text-caption text-fg-muted first:translate-x-0 last:-translate-x-full"
                style={{ left: `${String(position(tick, 1))}%` }}
              >
                {format.decimal(tick)}
              </span>
            ))}
          </div>
        </div>
      </div>
    </figure>
  );
}
