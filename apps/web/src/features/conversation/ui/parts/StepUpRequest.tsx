import { useTranslation } from 'react-i18next';

import { Button, LockIcon } from '@/shared/ui';

import { useConversation } from '../../model/context';
import { useMessage } from '../../model/message-context';

/** A write waits for a fresh code. The dialog opens on its own; this button opens it again after a cancel. */
export function StepUpRequest() {
  const { t } = useTranslation();
  const { message, interactive } = useMessage();
  const { stepUpAgain } = useConversation();
  if (!message.step_up_required) {
    return null;
  }
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-card border border-border bg-surface-sunken p-3">
      <p className="flex items-center gap-2 text-small text-fg">
        <LockIcon aria-hidden="true" size={18} />
        {t('chat.stepUpWaiting')}
      </p>
      {interactive && (
        <Button variant="secondary" size="sm" onClick={stepUpAgain}>
          {t('chat.stepUpAgain')}
        </Button>
      )}
    </div>
  );
}
