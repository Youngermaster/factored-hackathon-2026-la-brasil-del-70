import { useTranslation } from 'react-i18next';

import { Button, HumanIcon } from '@/shared/ui';

import { useConversation } from '../model/context';

/**
 * "Talk to a person", available on every turn. It sends the words the engine's deterministic signal reads, so the
 * kernel escalates in any state (ESC.human_requested) and the customer sees exactly what was asked.
 */
export function HumanButton() {
  const { t } = useTranslation();
  const { reply, inFlight, conversation } = useConversation();
  if (conversation?.status === 'escalated') {
    return (
      <p className="flex items-center gap-2 text-small text-fg-secondary">
        <HumanIcon aria-hidden="true" size={18} />
        {t('chat.withPerson')}
      </p>
    );
  }
  return (
    <Button
      variant="ghost"
      size="sm"
      disabled={inFlight}
      onClick={() => {
        reply({ kind: 'human' });
      }}
    >
      <HumanIcon aria-hidden="true" size={18} />
      {t('chat.human')}
    </Button>
  );
}
