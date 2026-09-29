import { useTranslation } from 'react-i18next';

import { useFormat } from '@/shared/i18n';
import { CardIcon } from '@/shared/ui';

import { useConversation } from '../../model/context';
import { useMessage } from '../../model/message-context';
import { Amount } from './Amount';
import { Masked } from './Masked';
import { PartCard } from './PartCard';

/**
 * Clarification options: one button per candidate, carrying its option id. A choice sends the ordinal the engine
 * reads ("Opción 2"), shown as the customer's message; the transaction id never leaves the server.
 */
export function Options() {
  const { t } = useTranslation();
  const format = useFormat();
  const { message, interactive } = useMessage();
  const { reply } = useConversation();
  const options = message.clarification?.options ?? [];
  if (options.length === 0) {
    return null;
  }
  return (
    <PartCard title={t('parts.options.title')}>
      <ol className="flex flex-col gap-2">
        {options.map((option, index) => (
          <li key={option.option_id}>
            <button
              type="button"
              data-option-id={option.option_id}
              disabled={!interactive}
              onClick={() => {
                reply({ kind: 'option', number: index + 1, optionId: option.option_id });
              }}
              className="flex w-full flex-wrap items-center justify-between gap-x-4 gap-y-1 rounded-control border border-border-strong bg-surface px-4 py-3 text-left text-small text-fg hover:bg-surface-hover disabled:opacity-60"
            >
              <span className="flex min-w-0 flex-col">
                <span className="font-semibold">
                  {t('parts.options.label', { number: index + 1 })}
                  {option.merchant_display === null ? '' : `: ${option.merchant_display}`}
                </span>
                <span className="text-fg-secondary">
                  <time dateTime={option.occurred_on}>{format.day(option.occurred_on)}</time>
                  {option.card_last4 !== null && (
                    <span className="ml-3 inline-flex items-center gap-1">
                      <CardIcon aria-hidden="true" size={16} />
                      <Masked last4={option.card_last4} />
                    </span>
                  )}
                </span>
              </span>
              <Amount value={option.amount} className="text-body" />
            </button>
          </li>
        ))}
      </ol>
    </PartCard>
  );
}
