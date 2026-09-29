import { useTranslation } from 'react-i18next';

import { Card, CardIcon, DisputeIcon, ReceiptIcon, WalletIcon, type Icon } from '@/shared/ui';

type Workflow = 'account_inquiry' | 'card_support' | 'dispute' | 'credit';

const WORKFLOWS: readonly { readonly id: Workflow; readonly icon: Icon }[] = [
  { id: 'account_inquiry', icon: WalletIcon },
  { id: 'card_support', icon: CardIcon },
  { id: 'dispute', icon: DisputeIcon },
  { id: 'credit', icon: ReceiptIcon },
];

const DOES = ['does1', 'does2', 'does3'] as const;
const DOES_NOT = ['not1', 'not2'] as const;

/**
 * What the system does and does not do in each workflow, that credit eligibility is indicative and synthetic,
 * and that the data is synthetic. Static copy in es, pt, and en.
 */
export function AboutPage() {
  const { t } = useTranslation();
  const notes = ['credit', 'data', 'transparency', 'human'] as const;
  return (
    <div className="flex flex-col gap-10">
      <div className="flex max-w-3xl flex-col gap-3">
        <h1 className="font-display text-display font-semibold tracking-tight text-fg">
          {t('about.title')}
        </h1>
        <p className="text-lead text-fg-secondary">{t('about.intro')}</p>
      </div>
      <ul className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {WORKFLOWS.map(({ id, icon: WorkflowIcon }) => (
          <li key={id}>
            <Card.Root aria-labelledby={`about-${id}`} className="h-full">
              <Card.Header
                title={
                  <span id={`about-${id}`} className="flex items-center gap-2">
                    <WorkflowIcon aria-hidden="true" size={22} />
                    {t(`home.topics.${id}`)}
                  </span>
                }
              />
              <Card.Body className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                <div className="flex flex-col gap-2">
                  <h3 className="text-small font-semibold text-fg">{t('about.does')}</h3>
                  <ul className="flex list-disc flex-col gap-1.5 pl-5 text-small text-fg">
                    {DOES.map((key) => (
                      <li key={key}>{t(`about.workflows.${id}.${key}`)}</li>
                    ))}
                  </ul>
                </div>
                <div className="flex flex-col gap-2">
                  <h3 className="text-small font-semibold text-fg">{t('about.doesNot')}</h3>
                  <ul className="flex list-disc flex-col gap-1.5 pl-5 text-small text-fg-secondary">
                    {DOES_NOT.map((key) => (
                      <li key={key}>{t(`about.workflows.${id}.${key}`)}</li>
                    ))}
                  </ul>
                </div>
              </Card.Body>
            </Card.Root>
          </li>
        ))}
      </ul>
      <div className="grid max-w-5xl grid-cols-1 gap-8 md:grid-cols-2">
        {notes.map((note) => (
          <section
            key={note}
            aria-labelledby={`about-note-${note}`}
            className="flex flex-col gap-2"
          >
            <h2 id={`about-note-${note}`} className="text-title font-semibold text-fg">
              {t(`about.${note}Title`)}
            </h2>
            <p className="max-w-prose text-body text-fg-secondary">{t(`about.${note}`)}</p>
          </section>
        ))}
      </div>
    </div>
  );
}
