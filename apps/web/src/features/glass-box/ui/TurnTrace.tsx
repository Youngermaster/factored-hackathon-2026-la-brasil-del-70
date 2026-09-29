import { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';

import { useTurnSelection } from '@/entities/turn-selection';
import { useFormat } from '@/shared/i18n';
import { cx } from '@/shared/lib/cx';
import { Badge, SwitchIcon, Timeline } from '@/shared/ui';

import type { TraceRecord } from '../api/trace';
import { isWorkflowId, outcomeTone, switchedWorkflow } from '../model/records';
import { RecordContext, type TraceView } from '../model/scope';
import { Clauses } from './sections/Clauses';
import { Credit } from './sections/Credit';
import { Decisions } from './sections/Decisions';
import { Internal } from './sections/Internal';
import { Outcome } from './sections/Outcome';
import { Tools } from './sections/Tools';
import { Understanding } from './sections/Understanding';
import { Versions } from './sections/Versions';

const EMPTY = new Map<string, string>();

/**
 * One turn's execution record: the state path and outcome at a glance, then understanding (blue), rules and
 * clauses (yellow), tools with verification, the credit panels, and versions and timing. Selecting it selects the
 * matching chat message, and the reverse.
 */
export function TurnTrace({
  record,
  index,
  latest,
  view,
  excerpts = EMPTY,
}: {
  readonly record: TraceRecord;
  readonly index: number;
  /** The newest turn opens by default; older ones show their summary line. */
  readonly latest: boolean;
  readonly view: TraceView;
  readonly excerpts?: ReadonlyMap<string, string> | undefined;
}) {
  const { t } = useTranslation();
  const format = useFormat();
  const selection = useTurnSelection();
  const selected = selection?.turnId === record.turn_id;
  const fromMessage = selection?.source === 'message';
  const ref = useRef<HTMLDetailsElement>(null);
  const scope = useMemo(() => ({ record, view, excerpts }), [record, view, excerpts]);
  const tone = outcomeTone(record.outcome);
  const [open, setOpen] = useState(latest);
  // Selecting the message opens its entry: state adjusted while rendering, when the selection changes.
  const reveal = selected && fromMessage;
  const [revealed, setRevealed] = useState(reveal);
  if (reveal !== revealed) {
    setRevealed(reveal);
    if (reveal) {
      setOpen(true);
    }
  }
  const workflowLabel = (id: string) => (isWorkflowId(id) ? t(`glass.workflows.${id}`) : id);

  useEffect(() => {
    if (reveal) {
      ref.current?.scrollIntoView({ block: 'nearest' });
    }
  }, [reveal]);

  return (
    <article
      aria-label={t('glass.turn', { number: index + 1 })}
      data-turn-id={record.turn_id}
      data-selected={selected || undefined}
      className={cx('rounded-card border bg-surface', selected ? 'border-fg' : 'border-border')}
    >
      <details
        ref={ref}
        open={open}
        onToggle={(event) => {
          setOpen(event.currentTarget.open);
        }}
        className="group"
      >
        <summary className="flex cursor-pointer list-none flex-col gap-1.5 p-4">
          <span className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-small font-semibold text-fg">
              {t('glass.turn', { number: index + 1 })}
            </span>
            <span className="font-mono text-caption text-fg-muted">
              <time dateTime={record.recorded_at}>{format.time(record.recorded_at)}</time>
            </span>
          </span>
          <span className="font-mono text-caption break-all text-fg-secondary">
            {record.state_before} {'->'} {record.state_after}
          </span>
          <span className="flex flex-wrap items-center gap-2">
            <Badge tone={tone === 'risk' ? 'risk' : 'neutral'}>
              {t(`glass.outcomes.${record.outcome}`)}
            </Badge>
            <Badge>{workflowLabel(record.workflow.id)}</Badge>
            {switchedWorkflow(record) && record.workflow_before !== null && (
              <Badge tone="understanding">
                <SwitchIcon aria-hidden="true" size={14} />
                {t('glass.switched', { from: workflowLabel(record.workflow_before.id) })}
              </Badge>
            )}
          </span>
        </summary>
        <div className="flex flex-col gap-4 border-t border-border p-4 text-small">
          {selection !== null && (
            <button
              type="button"
              aria-pressed={selected}
              onClick={() => {
                selection.select(selected ? null : record.turn_id, 'trace');
              }}
              className="w-fit rounded-control text-caption font-medium text-fg-secondary hover:text-fg"
            >
              {t('glass.showMessage')}
            </button>
          )}
          <RecordContext value={scope}>
            <Timeline.Root>
              <Understanding />
              <Decisions />
              <Clauses />
              <Tools />
              <Credit />
              <Outcome />
              <Versions />
            </Timeline.Root>
            <Internal />
          </RecordContext>
        </div>
      </details>
    </article>
  );
}
