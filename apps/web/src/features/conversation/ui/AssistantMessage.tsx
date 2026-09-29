import { useEffect, useMemo, useRef } from 'react';
import { useTranslation } from 'react-i18next';

import { useTurnSelection } from '@/entities/turn-selection';
import { LanguageScope } from '@/shared/i18n';
import { cx } from '@/shared/lib/cx';
import { TraceIcon } from '@/shared/ui';

import type { AssistantMessage as Message } from '../api/conversation';
import { MessageContext } from '../model/message-context';
import { withoutCitedParagraphs } from '../model/text';
import * as Parts from './parts';

/**
 * One assistant answer: the verified text (plain text, never HTML) and a renderer for every structured part the
 * API sends, in the answer's own language. On a page with the glass box, the answer links to its trace entry.
 */
export function AssistantMessage({
  turnId,
  message,
  interactive,
}: {
  readonly turnId: string;
  readonly message: Message;
  readonly interactive: boolean;
}) {
  const { t } = useTranslation();
  const selection = useTurnSelection();
  const selected = selection?.turnId === turnId;
  const fromTrace = selection?.source === 'trace';
  const ref = useRef<HTMLElement>(null);
  const scope = useMemo(() => ({ turnId, message, interactive }), [turnId, message, interactive]);

  useEffect(() => {
    if (selected && fromTrace) {
      ref.current?.scrollIntoView({ block: 'nearest' });
    }
  }, [selected, fromTrace]);

  return (
    <article
      ref={ref}
      aria-label={t('chat.assistant')}
      data-turn-id={turnId}
      data-selected={selected || undefined}
      className={cx(
        'flex max-w-full flex-col gap-3 border-l-2 pl-4 sm:max-w-[90%]',
        selected ? 'border-fg' : 'border-transparent',
      )}
    >
      <LanguageScope language={message.language}>
        <MessageContext value={scope}>
          <Parts.Notices />
          <p className="text-body whitespace-pre-line text-fg">
            {withoutCitedParagraphs(message.text, message.citations)}
          </p>
          <Parts.Options />
          <Parts.Confirmation />
          <Parts.Balances />
          <Parts.Payments />
          <Parts.Statement />
          <Parts.CardStatus />
          <Parts.CreditProducts />
          <Parts.Eligibility />
          <Parts.ActionStatuses />
          <Parts.Escalation />
          <Parts.StepUpRequest />
          <Parts.Citations />
        </MessageContext>
      </LanguageScope>
      {selection !== null && (
        <button
          type="button"
          aria-pressed={selected}
          onClick={() => {
            selection.select(selected ? null : turnId, 'message');
          }}
          className="inline-flex w-fit items-center gap-1.5 rounded-control text-caption font-medium text-fg-secondary hover:text-fg"
        >
          <TraceIcon aria-hidden="true" size={16} />
          {t('chat.showTrace')}
        </button>
      )}
    </article>
  );
}
