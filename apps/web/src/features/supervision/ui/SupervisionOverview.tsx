import { useTranslation } from 'react-i18next';

import { errorMessageKey, errorRequestId } from '@/shared/api';
import { useFormat } from '@/shared/i18n';
import { Badge, Button, ErrorState, InfoIcon, Skeleton, SkeletonGroup } from '@/shared/ui';

import { useModelInventory } from '../api/supervision';
import { EndToEnd } from './EndToEnd';
import { LanguageModel } from './LanguageModel';
import { LiveOperations } from './LiveOperations';
import { OfflineEvidence } from './OfflineEvidence';
import { ServedModels } from './ServedModels';
import { WhoDecides } from './WhoDecides';

/**
 * The supervision view (evaluator role): who decides each step, the models in service, their offline evidence and
 * the promotion decisions, the end-to-end evaluation, the language model setup, and the live degradation level.
 * Each source loads and fails on its own, so one failing request never blanks the page.
 */
export function SupervisionOverview() {
  const { t } = useTranslation();
  const format = useFormat();
  const inventory = useModelInventory();

  let modelSections;
  if (inventory.isPending) {
    modelSections = (
      <SkeletonGroup label={t('supervision.loading')}>
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-64 w-full" />
      </SkeletonGroup>
    );
  } else if (inventory.isError) {
    modelSections = (
      <ErrorState
        title={t('supervision.error')}
        description={t(errorMessageKey(inventory.error))}
        requestId={errorRequestId(inventory.error)}
        action={
          <Button variant="secondary" onClick={() => void inventory.refetch()}>
            {t('common.retry')}
          </Button>
        }
      />
    );
  } else {
    const { inventory: served, cards } = inventory.data;
    modelSections = (
      <>
        <p className="text-caption text-fg-muted">
          {t('supervision.servingSince', { time: format.dateTime(served.generated_at) })}
        </p>
        <WhoDecides inventory={served} />
        <ServedModels inventory={served} />
        <OfflineEvidence cards={cards.cards} promotions={cards.promotions} inventory={served} />
      </>
    );
  }

  return (
    <div className="flex flex-col gap-10">
      <header className="flex max-w-3xl flex-col gap-3 border-b border-border pb-7">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="neutral">{t('supervision.restricted')}</Badge>
        </div>
        <h1 className="font-display text-heading font-semibold tracking-tight text-fg">
          {t('supervision.heading')}
        </h1>
        <p className="text-body text-fg-secondary">{t('supervision.intro')}</p>
      </header>
      {modelSections}
      <EndToEnd />
      {inventory.isSuccess && <LanguageModel inventory={inventory.data.inventory} />}
      <LiveOperations />
      <section
        aria-labelledby="supervision-provenance"
        className="flex gap-3 rounded-card border border-understanding bg-understanding-subtle p-5"
      >
        <InfoIcon
          aria-hidden="true"
          size={20}
          className="mt-0.5 shrink-0 text-understanding-text"
        />
        <div>
          <h2 id="supervision-provenance" className="text-body font-semibold text-fg">
            {t('supervision.provenance.title')}
          </h2>
          <p className="mt-1 text-small text-fg-secondary">{t('supervision.provenance.body')}</p>
        </div>
      </section>
    </div>
  );
}
