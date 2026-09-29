import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

import { Badge, Button, NewIcon } from '@/shared/ui';

import { useConversation } from '../model/context';

/** The chat's title bar: the page title, the conversation status, a new conversation, and page actions (a slot). */
export function Header({ children }: { readonly children?: ReactNode }) {
  const { t } = useTranslation();
  const { conversation, startNew, conversationId } = useConversation();
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex min-w-0 items-center gap-3">
        <h1 className="font-display text-heading font-semibold tracking-tight text-fg">
          {t('chat.title')}
        </h1>
        {conversation?.status === 'escalated' && (
          <Badge tone="risk">{t('chat.status.escalated')}</Badge>
        )}
        {conversation?.status === 'closed' && <Badge>{t('chat.status.closed')}</Badge>}
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {children}
        {conversationId !== null && (
          <Button variant="secondary" size="sm" onClick={startNew}>
            <NewIcon aria-hidden="true" size={16} />
            {t('chat.newConversation')}
          </Button>
        )}
      </div>
    </div>
  );
}
