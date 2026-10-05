import { useTranslation } from 'react-i18next';

import { Badge, DataTable, type BadgeTone } from '@/shared/ui';

import type { ModelInventory, ServedModel } from '../api/supervision';
import { useSupervisionLabels } from './labels';
import { Section } from './Section';

/** Trained models are model understanding (blue); rule-based baselines are deterministic (yellow). */
const KIND_TONE: Record<ServedModel['kind'], BadgeTone> = {
  learned: 'understanding',
  baseline: 'decision',
  unavailable: 'risk',
};

/** The components this process serves, as recorded at startup: selection, concrete version, kind, fallback. */
export function ServedModels({ inventory }: { readonly inventory: ModelInventory }) {
  const { t } = useTranslation();
  const labels = useSupervisionLabels();
  return (
    <Section
      id="supervision-models"
      title={t('supervision.models.title')}
      intro={t('supervision.models.intro')}
    >
      <DataTable.Root caption={t('supervision.models.caption')} captionHidden>
        <DataTable.Head>
          <tr>
            <DataTable.HeaderCell>{t('supervision.models.component')}</DataTable.HeaderCell>
            <DataTable.HeaderCell>{t('supervision.models.selected')}</DataTable.HeaderCell>
            <DataTable.HeaderCell>{t('supervision.models.served')}</DataTable.HeaderCell>
            <DataTable.HeaderCell>{t('supervision.models.kind')}</DataTable.HeaderCell>
            <DataTable.HeaderCell>{t('supervision.models.fallback')}</DataTable.HeaderCell>
          </tr>
        </DataTable.Head>
        <DataTable.Body>
          {inventory.components.map((item) => (
            <DataTable.Row key={item.component}>
              <th scope="row" className="px-4 py-3 text-left align-top font-medium text-fg">
                {labels.component(item.component)}
              </th>
              <DataTable.Cell className="font-mono text-caption">{item.selected}</DataTable.Cell>
              <DataTable.Cell>
                {item.served === null ? (
                  <span className="text-fg-muted">{t('supervision.models.none')}</span>
                ) : (
                  <span className="flex flex-col gap-0.5">
                    <span className="font-mono text-caption break-all">{item.served}</span>
                    {item.alias !== null && (
                      <span className="text-caption text-fg-muted">
                        {t('supervision.models.alias', { alias: item.alias })}
                      </span>
                    )}
                  </span>
                )}
              </DataTable.Cell>
              <DataTable.Cell>
                <Badge tone={KIND_TONE[item.kind]}>{labels.kind(item.kind)}</Badge>
              </DataTable.Cell>
              <DataTable.Cell>
                {item.reason === null ? (
                  <span className="text-fg-muted">{t('supervision.models.noFallback')}</span>
                ) : (
                  <Badge tone="risk">{labels.fallbackReason(item.reason)}</Badge>
                )}
              </DataTable.Cell>
            </DataTable.Row>
          ))}
        </DataTable.Body>
      </DataTable.Root>
      <p className="text-caption text-fg-muted">{t('supervision.models.riskNote')}</p>
    </Section>
  );
}
