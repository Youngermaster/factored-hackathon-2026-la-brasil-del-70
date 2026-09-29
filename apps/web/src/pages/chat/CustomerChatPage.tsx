import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { TurnSelectionProvider } from '@/entities/turn-selection';
import { SessionStatus } from '@/features/auth';
import { AssistantProfileControl } from '@/features/assistant-profile';
import { Conversation, useConversation } from '@/features/conversation';
import { GlassBox } from '@/features/glass-box';
import { cx } from '@/shared/lib/cx';
import { Button, ExternalIcon, PanelIcon } from '@/shared/ui';

/**
 * The customer chat with the glass box beside it (a panel on wide screens, a sheet on narrow ones). The page
 * provides the linked selection between messages and trace entries; the features do the rest.
 */
export function CustomerChatPage() {
  return (
    <TurnSelectionProvider>
      <Conversation.Root>
        <ChatLayout />
      </Conversation.Root>
    </TurnSelectionProvider>
  );
}

function ChatLayout() {
  const { t } = useTranslation();
  const { conversationId, turns } = useConversation();
  const [traceOpen, setTraceOpen] = useState(true);
  return (
    <div
      className={cx(
        'grid grid-cols-1 gap-8',
        traceOpen && 'lg:grid-cols-[minmax(0,1fr)_minmax(0,26rem)]',
      )}
    >
      <div className="flex min-w-0 flex-col gap-6">
        <Conversation.Header>
          <AssistantProfileControl />
          <div className="lg:hidden">
            <GlassBox.SheetTrigger conversationId={conversationId} />
          </div>
          <div className="hidden lg:block">
            <Button
              variant="secondary"
              size="sm"
              aria-expanded={traceOpen}
              aria-controls="glass-box"
              onClick={() => {
                setTraceOpen((open) => !open);
              }}
            >
              <PanelIcon aria-hidden="true" size={16} />
              {traceOpen ? t('chat.hideTracePanel') : t('chat.showTracePanel')}
            </Button>
          </div>
          {conversationId !== null && (
            <Button asChild variant="ghost" size="sm">
              <Link to={`/glass-box/${conversationId}`}>
                <ExternalIcon aria-hidden="true" size={16} />
                {t('chat.traceFull')}
              </Link>
            </Button>
          )}
        </Conversation.Header>
        <Conversation.Starters />
        <Conversation.Messages />
        <div className="sticky bottom-0 z-10 -mx-4 flex flex-col gap-2 border-t border-border bg-canvas px-4 pt-3 pb-4 sm:-mx-6 sm:px-6">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <Conversation.HumanButton />
          </div>
          <Conversation.Composer />
        </div>
        {turns.length === 0 && <SessionStatus />}
      </div>
      {traceOpen && (
        <div id="glass-box" className="hidden lg:sticky lg:top-20 lg:block lg:self-start">
          <GlassBox.Panel
            conversationId={conversationId}
            className="lg:max-h-[calc(100dvh-6rem)] lg:overflow-y-auto lg:pr-1"
          />
        </div>
      )}
    </div>
  );
}
