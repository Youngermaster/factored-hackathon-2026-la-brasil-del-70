import { useTranslation } from 'react-i18next';

import { useFormat } from '@/shared/i18n';

import type { ChannelSide, HumanMessage, HumanServiceView } from '../api/channel';

/** Only the human exchange: historical assistant turns stay in the customer's existing timeline. */
export function HumanTimeline({
  view,
  messages,
  side = 'customer',
}: {
  readonly view: HumanServiceView;
  readonly messages: readonly HumanMessage[];
  readonly side?: ChannelSide;
}) {
  const { t } = useTranslation();
  const format = useFormat();
  return (
    <section
      aria-label={t('humanService.title')}
      className="flex flex-col gap-4 border-t border-border pt-4"
    >
      <h2 className="text-small font-semibold text-fg">{t('humanService.title')}</h2>
      <p role="status" className="text-small text-fg-secondary">
        {t(`humanService.status.${view.status}`)}
      </p>
      <div
        role="log"
        aria-live="polite"
        aria-label={t('humanService.messages')}
        className="flex flex-col gap-4"
      >
        <ol className="flex flex-col gap-4">
          {messages.map((message) => (
            <li key={message.message_id} className="flex flex-col gap-1">
              <div className="flex flex-wrap gap-2 text-caption text-fg-muted">
                <span className="font-semibold">
                  {t(
                    `humanService.author.${message.role === 'user' && side === 'agent' ? 'customer' : message.role}`,
                  )}
                </span>
                <time dateTime={message.sent_at}>{format.dateTime(message.sent_at)}</time>
              </div>
              <p className="whitespace-pre-wrap break-words text-body text-fg">{message.text}</p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
