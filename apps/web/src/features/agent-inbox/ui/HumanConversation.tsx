import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useId, useState, type SyntheticEvent } from 'react';
import { useTranslation } from 'react-i18next';

import { HumanTimeline, useHumanChannel, useSendHumanMessage } from '@/features/human-service';
import { errorMessageKey, hasProblem, queryKeys } from '@/shared/api';
import { Button, ErrorState, Textarea } from '@/shared/ui';

import { useHandoffView } from '../model/handoff-context';

/** Only the assigned agent can read the exchange or reply. The handoff remains the escalation context. */
export function HumanConversation() {
  const { t } = useTranslation();
  const handoff = useHandoffView();
  const channel = useHumanChannel('agent', handoff.status === 'open' ? null : handoff.handoff_id);
  const cache = useQueryClient();
  useEffect(() => {
    if (channel.view?.status === 'closed' && handoff.status !== 'resolved') {
      void cache.invalidateQueries({ queryKey: queryKeys.handoffs.detail(handoff.handoff_id) });
    }
  }, [cache, channel.view?.status, handoff.status, handoff.handoff_id]);
  const send = useSendHumanMessage('agent');
  const id = useId();
  const [draft, setDraft] = useState('');
  const [delivery, setDelivery] = useState<{ messageId: string; text: string } | null>(null);
  if (handoff.status === 'open') return null;
  if (channel.error !== null && hasProblem(channel.error, 'resource-not-found')) {
    return <p className="text-small text-fg-secondary">{t('humanService.assignedElsewhere')}</p>;
  }
  const closed = channel.view?.status === 'closed' || handoff.status === 'resolved';
  const submit = (event: SyntheticEvent) => {
    event.preventDefault();
    const text = draft.trim();
    if (closed || send.isPending || text === '') return;
    const next = delivery?.text === text ? delivery : { messageId: crypto.randomUUID(), text };
    setDelivery(next);
    send.mutate(
      { id: handoff.handoff_id, ...next },
      {
        onSuccess: () => {
          setDraft('');
          setDelivery(null);
        },
      },
    );
  };
  return (
    <div className="flex flex-col gap-4">
      {channel.view !== null && (
        <HumanTimeline side="agent" view={channel.view} messages={channel.messages} />
      )}
      {channel.isPending && <p role="status">{t('humanService.loading')}</p>}
      {channel.error !== null && (
        <ErrorState
          title={t('humanService.disconnected')}
          description={t('humanService.reconnectBody')}
          action={
            <Button variant="secondary" onClick={() => void channel.refetch()}>
              {t('common.retry')}
            </Button>
          }
        />
      )}
      {!closed && (
        <form onSubmit={submit} className="flex flex-col gap-2">
          <label htmlFor={id} className="text-small font-medium text-fg">
            {t('humanService.replyLabel')}
          </label>
          <Textarea
            id={id}
            value={draft}
            maxLength={4000}
            readOnly={send.isPending}
            rows={3}
            onChange={(event) => {
              setDraft(event.target.value);
            }}
          />
          {send.isError && (
            <p role="alert" className="text-small text-risk-text">
              {t(errorMessageKey(send.error))}
            </p>
          )}
          <Button
            type="submit"
            pending={send.isPending}
            disabled={draft.trim() === '' || channel.view === null}
          >
            {send.isError ? t('common.retry') : t('humanService.replySend')}
          </Button>
        </form>
      )}
    </div>
  );
}
