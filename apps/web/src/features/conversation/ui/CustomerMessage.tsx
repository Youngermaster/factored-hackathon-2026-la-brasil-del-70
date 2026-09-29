import { useTranslation } from 'react-i18next';

import { errorMessageKey, isApiError } from '@/shared/api';
import { cx } from '@/shared/lib/cx';
import { Button, RetryIcon, WarningIcon } from '@/shared/ui';

import { useConversation } from '../model/context';
import type { PendingTurn } from '../model/pending';

function retryable(error: unknown): boolean {
  return !isApiError(error) || error.status >= 500 || error.status === 429;
}

/** The customer's own words, rendered as sent; a message still in flight or failed says so, with a retry. */
export function CustomerMessage({
  text,
  pending,
}: {
  readonly text: string;
  readonly pending?: PendingTurn;
}) {
  const { t } = useTranslation();
  const { retry, inFlight } = useConversation();
  const failed = pending?.status === 'failed';
  return (
    <div className="flex flex-col items-end gap-1.5">
      <p className="sr-only">{t('chat.you')}</p>
      <p
        className={cx(
          'max-w-[85%] rounded-card bg-surface-sunken px-4 py-2.5 text-body whitespace-pre-line text-fg sm:max-w-[75%]',
          pending?.status === 'sending' && 'opacity-70',
          failed && 'border border-risk',
        )}
      >
        {text}
      </p>
      {pending?.status === 'sending' && (
        <p className="text-caption text-fg-muted">{t('chat.sending')}</p>
      )}
      {failed && (
        <div role="alert" className="flex flex-wrap items-center justify-end gap-2">
          <p className="flex items-center gap-1.5 text-small text-risk-text">
            <WarningIcon aria-hidden="true" size={16} />
            {t('chat.notSent')} {t(errorMessageKey(pending.error))}
          </p>
          {retryable(pending.error) && (
            <Button
              variant="secondary"
              size="sm"
              disabled={inFlight}
              onClick={() => {
                retry(pending.turnId);
              }}
            >
              <RetryIcon aria-hidden="true" size={16} />
              {t('chat.retry')}
            </Button>
          )}
        </div>
      )}
    </div>
  );
}
