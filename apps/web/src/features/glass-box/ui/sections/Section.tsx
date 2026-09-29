import type { ReactNode } from 'react';

import { Timeline, type TimelineTone } from '@/shared/ui';

/**
 * One step of a turn's trace. The marker color repeats the meaning the kind label states: blue for what the
 * language model and other models understood, yellow for rules and verified actions, red for escalations and
 * failures, neutral for data reads and versions.
 */
export function Section({
  tone,
  title,
  kind,
  meta,
  children,
}: {
  readonly tone: TimelineTone;
  readonly title: ReactNode;
  /** The words for the tone ("Model understanding", "Rules"), so color never carries meaning alone. */
  readonly kind?: ReactNode;
  readonly meta?: ReactNode;
  readonly children?: ReactNode;
}) {
  return (
    <Timeline.Item
      tone={tone}
      title={
        <span className="flex flex-wrap items-baseline gap-x-2">
          {title}
          {kind !== undefined && (
            <span className="text-caption font-normal text-fg-muted">{kind}</span>
          )}
        </span>
      }
      meta={meta}
    >
      {children}
    </Timeline.Item>
  );
}
