import { useId, type KeyboardEvent, type SyntheticEvent } from 'react';
import { useTranslation } from 'react-i18next';

import { cx } from '@/shared/lib/cx';
import { Button, SendIcon, Textarea } from '@/shared/ui';

import { MAX_MESSAGE_LENGTH, useConversation } from '../model/context';

/**
 * The message box: a visible character counter, Enter to send, Shift+Enter for a new line, and no sending while a
 * turn is in flight. The counter is not a live region (it would speak on every key); reaching the limit is
 * announced once.
 */
export function Composer({ className }: { readonly className?: string }) {
  const { t } = useTranslation();
  const { send, inFlight, composerRef, draft, setDraft } = useConversation();
  const id = useId();
  const hintId = `${id}-hint`;
  const counterId = `${id}-counter`;
  const atLimit = draft.length >= MAX_MESSAGE_LENGTH;
  const canSend = !inFlight && draft.trim() !== '';

  const submit = (event?: SyntheticEvent) => {
    event?.preventDefault();
    if (!canSend) {
      return;
    }
    send(draft);
    setDraft('');
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      submit();
    }
  };

  return (
    <form onSubmit={submit} className={cx('flex flex-col gap-2', className)}>
      <label htmlFor={id} className="sr-only">
        {t('chat.composerLabel')}
      </label>
      <div className="flex items-end gap-2">
        <Textarea
          id={id}
          ref={composerRef}
          value={draft}
          compact
          rows={2}
          maxLength={MAX_MESSAGE_LENGTH}
          readOnly={inFlight}
          aria-describedby={`${hintId} ${counterId}`}
          onChange={(event) => {
            setDraft(event.target.value);
          }}
          onKeyDown={onKeyDown}
          className="max-h-48 flex-1 resize-y"
        />
        <Button type="submit" size="lg" disabled={!canSend} className="px-4">
          <SendIcon aria-hidden="true" size={20} />
          <span className="sr-only sm:not-sr-only">{t('chat.send')}</span>
        </Button>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 text-caption text-fg-muted">
        <p id={hintId}>{inFlight ? t('chat.waiting') : t('chat.composerHint')}</p>
        <p id={counterId} className={cx('font-mono tabular-nums', atLimit && 'text-risk-text')}>
          {t('chat.counter', { count: draft.length, max: MAX_MESSAGE_LENGTH })}
        </p>
      </div>
      <p role="status" className="sr-only">
        {atLimit ? t('chat.limitReached', { max: MAX_MESSAGE_LENGTH }) : ''}
      </p>
    </form>
  );
}
