import { useTranslation } from 'react-i18next';

import { CardIcon, DisputeIcon, ReceiptIcon, WalletIcon, type Icon } from '@/shared/ui';

import { useConversation } from '../model/context';

type Topic = 'account_inquiry' | 'card_support' | 'dispute' | 'credit';

const TOPICS: readonly { readonly id: Topic; readonly icon: Icon }[] = [
  { id: 'account_inquiry', icon: WalletIcon },
  { id: 'card_support', icon: CardIcon },
  { id: 'dispute', icon: DisputeIcon },
  { id: 'credit', icon: ReceiptIcon },
];

/**
 * Before the first message: what the assistant handles, one topic per workflow. Choosing a topic writes an example
 * into the message box (it never sends on its own), so the customer can edit it first.
 */
export function Starters() {
  const { t } = useTranslation();
  const { turns, pending, loadStatus, setDraft, composerRef } = useConversation();
  if (turns.length > 0 || pending.length > 0 || loadStatus !== 'new') {
    return null;
  }
  return (
    <section aria-labelledby="starters-title" className="flex flex-col gap-4">
      <div className="flex max-w-2xl flex-col gap-2">
        <h2 id="starters-title" className="text-title font-semibold text-fg">
          {t('home.heading')}
        </h2>
        <p className="text-body text-fg-secondary">{t('home.intro')}</p>
      </div>
      <ul className="grid grid-cols-1 gap-px overflow-hidden rounded-card border border-border bg-border sm:grid-cols-2">
        {TOPICS.map(({ id, icon: TopicIcon }) => (
          <li key={id} className="bg-surface">
            <button
              type="button"
              onClick={() => {
                setDraft(t(`home.topics.${id}Example`));
                composerRef.current?.focus();
              }}
              className="flex h-full w-full gap-4 p-5 text-left hover:bg-surface-hover"
            >
              <TopicIcon aria-hidden="true" size={24} className="mt-0.5 shrink-0 text-fg" />
              <span className="flex flex-col gap-1">
                <span className="text-body font-semibold text-fg">{t(`home.topics.${id}`)}</span>
                <span className="text-small text-fg-secondary">{t(`home.topics.${id}Body`)}</span>
                <span className="text-small text-fg-muted">
                  {t('home.tryExample', { example: t(`home.topics.${id}Example`) })}
                </span>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </section>
  );
}
