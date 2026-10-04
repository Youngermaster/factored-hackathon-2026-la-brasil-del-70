import { Fragment, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';

import { HumanTimeline } from '@/features/human-service';

import { errorMessageKey, errorRequestId, hasProblem } from '@/shared/api';
import {
  Button,
  EmptyState,
  ErrorState,
  InfoIcon,
  LockIcon,
  Skeleton,
  SkeletonGroup,
} from '@/shared/ui';

import { useConversation } from '../model/context';
import { AssistantMessage } from './AssistantMessage';
import { CustomerMessage } from './CustomerMessage';

/**
 * The message list: a polite live log, so each new answer is read once without moving focus. New content scrolls
 * into view; when the control that sent a message is gone or disabled, focus returns to the composer.
 */
export function Messages({ className = '' }: { readonly className?: string }) {
  const { t } = useTranslation();
  const conversation = useConversation();
  const { turns, pending, notices, inFlight, latestTurnId, loadStatus, composerRef } = conversation;
  const endRef = useRef<HTMLLIElement>(null);
  const count = turns.length + pending.length + conversation.humanMessages.length;

  useEffect(() => {
    if (count === 0) {
      return;
    }
    endRef.current?.scrollIntoView({ block: 'end' });
    const active = document.activeElement;
    const stranded =
      active === null ||
      active === document.body ||
      (active instanceof HTMLButtonElement && active.disabled);
    if (stranded && !inFlight) {
      composerRef.current?.focus({ preventScroll: true });
    }
  }, [count, inFlight, composerRef]);

  if (conversation.creationError) {
    return (
      <ErrorState
        title={t('chat.loadError')}
        description={
          hasProblem(conversation.creationError, 'conversation-creation-limited')
            ? t('humanService.creationLimit')
            : t(errorMessageKey(conversation.creationError))
        }
        action={
          <Button variant="secondary" onClick={conversation.startNew}>
            {t('common.retry')}
          </Button>
        }
      />
    );
  }
  if (loadStatus === 'loading') {
    return (
      <SkeletonGroup label={t('chat.loading')} className={className}>
        <Skeleton className="ml-auto h-10 w-2/3" />
        <Skeleton className="h-24 w-4/5" />
      </SkeletonGroup>
    );
  }
  if (loadStatus === 'not_found') {
    return (
      <EmptyState
        className={className}
        title={t('chat.notFoundTitle')}
        description={t('chat.notFoundBody')}
        action={
          <Button variant="secondary" onClick={conversation.startNew}>
            {t('chat.newConversation')}
          </Button>
        }
      />
    );
  }
  if (loadStatus === 'error') {
    return (
      <ErrorState
        className={className}
        title={t('chat.loadError')}
        description={t(errorMessageKey(conversation.loadError))}
        requestId={errorRequestId(conversation.loadError)}
        action={
          <Button variant="secondary" onClick={conversation.reload}>
            {t('common.retry')}
          </Button>
        }
      />
    );
  }

  return (
    <div role="log" aria-live="polite" aria-label={t('chat.messagesLabel')} className={className}>
      <h2 className="sr-only">{t('chat.messagesLabel')}</h2>
      <ol className="flex flex-col gap-6">
        {conversation.conversationId !== null && turns.length > 0 && (
          <li className="flex items-center gap-2 text-caption text-fg-muted">
            <InfoIcon aria-hidden="true" size={14} />
            <span>
              {t('chat.reference')}{' '}
              <span className="font-mono select-all">{conversation.conversationId}</span>
            </span>
          </li>
        )}
        {turns.map((turn) => (
          <Fragment key={turn.turn_id}>
            <li>
              <CustomerMessage text={turn.customer_text} />
            </li>
            {turn.message !== null && (
              <li>
                <AssistantMessage
                  turnId={turn.turn_id}
                  message={turn.message}
                  interactive={
                    turn.turn_id === latestTurnId && !inFlight && !conversation.humanMode
                  }
                />
              </li>
            )}
            {notices
              .filter((notice) => notice.afterTurnId === turn.turn_id)
              .map((notice) => (
                <li
                  key={notice.id}
                  className="flex items-center gap-2 text-small text-fg-secondary"
                >
                  <LockIcon aria-hidden="true" size={16} />
                  {t('chat.stepUpCancelled')}
                </li>
              ))}
          </Fragment>
        ))}
        {conversation.humanView !== null && (
          <li>
            <HumanTimeline view={conversation.humanView} messages={conversation.humanMessages} />
          </li>
        )}
        {conversation.humanError !== null && (
          <li>
            <ErrorState
              title={t('humanService.disconnected')}
              description={t('humanService.reconnectBody')}
              action={
                <Button variant="secondary" onClick={conversation.humanReload}>
                  {t('common.retry')}
                </Button>
              }
            />
          </li>
        )}
        {pending.map((turn) => (
          <li key={turn.turnId}>
            <CustomerMessage text={turn.text} pending={turn} />
          </li>
        ))}
        {inFlight && (
          <li role="status" className="flex items-center gap-2 text-small text-fg-muted">
            <span aria-hidden="true" className="size-2 rounded-full bg-fg-muted animate-skeleton" />
            {conversation.humanMode ? t('humanService.sending') : t('chat.responding')}
          </li>
        )}
        <li ref={endRef} aria-hidden="true" className="h-px" />
      </ol>
    </div>
  );
}
