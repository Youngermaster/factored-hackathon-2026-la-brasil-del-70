import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router';

import { SessionStatus } from '@/features/auth';
import { CardIcon, ChatIcon, DisputeIcon, ReceiptIcon, WalletIcon, type Icon } from '@/shared/ui';

type Topic = 'account_inquiry' | 'card_support' | 'dispute' | 'credit';

const TOPICS: readonly { readonly id: Topic; readonly icon: Icon }[] = [
  { id: 'account_inquiry', icon: WalletIcon },
  { id: 'card_support', icon: CardIcon },
  { id: 'dispute', icon: DisputeIcon },
  { id: 'credit', icon: ReceiptIcon },
];

/**
 * The customer's start: what the assistant handles (the four workflows), the session, and, after a
 * re-authentication, the conversation that is still open. Phase 13 adds the chat itself.
 */
export function CustomerHomePage() {
  const { t } = useTranslation();
  const [params] = useSearchParams();
  const conversation = params.get('conversation');

  return (
    <div className="flex flex-col gap-10">
      <div className="flex max-w-2xl flex-col gap-3">
        <h1 className="font-display text-display font-semibold tracking-tight text-fg">
          {t('home.heading')}
        </h1>
        <p className="text-lead text-fg-secondary">{t('home.intro')}</p>
      </div>

      {conversation !== null && (
        <p
          role="status"
          className="flex items-center gap-2 rounded-card border border-border bg-surface px-4 py-3 text-small text-fg"
        >
          <ChatIcon aria-hidden="true" size={20} className="shrink-0 text-fg-secondary" />
          {t('home.resume', { id: conversation })}
        </p>
      )}

      <section aria-labelledby="topics-title" className="flex flex-col gap-4">
        <h2 id="topics-title" className="text-title font-semibold text-fg">
          {t('home.topicsLabel')}
        </h2>
        <ul className="grid grid-cols-1 gap-px overflow-hidden rounded-card border border-border bg-border sm:grid-cols-2">
          {TOPICS.map(({ id, icon: TopicIcon }) => (
            <li key={id} className="flex gap-4 bg-surface p-5 sm:p-6">
              <TopicIcon aria-hidden="true" size={24} className="mt-0.5 shrink-0 text-fg" />
              <div className="flex flex-col gap-1">
                <h3 className="text-body font-semibold text-fg">{t(`home.topics.${id}`)}</h3>
                <p className="text-small text-fg-secondary">{t(`home.topics.${id}Body`)}</p>
              </div>
            </li>
          ))}
        </ul>
      </section>

      <SessionStatus />
    </div>
  );
}
