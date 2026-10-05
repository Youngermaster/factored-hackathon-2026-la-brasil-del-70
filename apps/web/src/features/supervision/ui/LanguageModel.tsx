import { useTranslation } from 'react-i18next';

import { useFormat } from '@/shared/i18n';
import { Badge, DataTable, KeyValueList, type BadgeTone } from '@/shared/ui';

import type { ModelInventory } from '../api/supervision';
import { useSupervisionLabels } from './labels';
import { Section } from './Section';

const BASIS_TONE: Record<ModelInventory['llm']['models'][number]['price_basis'], BadgeTone> = {
  verified: 'decision',
  unverified: 'neutral',
  unknown_model: 'risk',
};

const FEATURES = ['understanding', 'phrasing', 'handoff_summary'] as const;

/**
 * The language model setup: provider and models with the price basis the cost metrics charge, which model features
 * are on, the budget limits, and every prompt version with whether the flags let it run.
 */
export function LanguageModel({ inventory }: { readonly inventory: ModelInventory }) {
  const { t } = useTranslation();
  const format = useFormat();
  const labels = useSupervisionLabels();
  const { llm } = inventory;
  const usd = (amount: string) => format.money({ amount, currency: 'USD' });
  const onOff = (on: boolean) => (
    <Badge tone={on ? 'understanding' : 'neutral'}>
      {on ? t('supervision.llm.on') : t('supervision.llm.off')}
    </Badge>
  );
  return (
    <Section
      id="supervision-llm"
      title={t('supervision.llm.title')}
      intro={t('supervision.llm.intro')}
    >
      <div className="flex flex-col gap-5 rounded-card border border-border bg-surface p-5">
        <KeyValueList.Root columns={3}>
          <KeyValueList.Item label={t('supervision.llm.provider')}>
            <span className="font-mono">{llm.provider}</span>
          </KeyValueList.Item>
          <KeyValueList.Item label={t('supervision.llm.dailyBudget')} numeric>
            {usd(llm.daily_budget_usd)}
          </KeyValueList.Item>
          <KeyValueList.Item label={t('supervision.llm.conversationBudget')} numeric>
            {usd(llm.conversation_budget_usd)}
          </KeyValueList.Item>
          <KeyValueList.Item label={t('supervision.llm.sessionTokens')} numeric>
            {format.number(llm.session_token_limit)}
          </KeyValueList.Item>
          <KeyValueList.Item label={t('supervision.llm.multiplier')} numeric>
            {t('supervision.llm.multiplierValue', { value: llm.unverified_price_multiplier })}
          </KeyValueList.Item>
        </KeyValueList.Root>
        {!llm.configured && (
          <p className="rounded-control border border-border-strong bg-surface-sunken px-3 py-2 text-small text-fg">
            {t('supervision.llm.none')}
          </p>
        )}
        <div className="flex flex-col gap-2">
          <h3 className="text-small font-semibold text-fg">{t('supervision.llm.features')}</h3>
          <ul className="flex flex-wrap gap-x-6 gap-y-2">
            {FEATURES.map((feature) => (
              <li key={feature} className="flex items-center gap-2 text-small text-fg">
                {t(`supervision.llm.${feature}`)}
                {onOff(llm[feature] && llm.configured)}
              </li>
            ))}
          </ul>
        </div>
      </div>
      {llm.models.length > 0 && (
        <DataTable.Root caption={t('supervision.llm.caption')}>
          <DataTable.Head>
            <tr>
              <DataTable.HeaderCell>{t('supervision.llm.role')}</DataTable.HeaderCell>
              <DataTable.HeaderCell>{t('supervision.llm.model')}</DataTable.HeaderCell>
              <DataTable.HeaderCell>{t('supervision.llm.basis')}</DataTable.HeaderCell>
              <DataTable.HeaderCell numeric>{t('supervision.llm.input')}</DataTable.HeaderCell>
              <DataTable.HeaderCell numeric>{t('supervision.llm.output')}</DataTable.HeaderCell>
              <DataTable.HeaderCell>{t('supervision.llm.listedOn')}</DataTable.HeaderCell>
            </tr>
          </DataTable.Head>
          <DataTable.Body>
            {llm.models.map((model) => (
              <DataTable.Row key={model.role}>
                <th scope="row" className="px-4 py-3 text-left align-top font-medium text-fg">
                  {labels.llmRole(model.role)}
                </th>
                <DataTable.Cell className="font-mono text-caption">{model.model_id}</DataTable.Cell>
                <DataTable.Cell>
                  <Badge tone={BASIS_TONE[model.price_basis]}>
                    {labels.priceBasis(model.price_basis)}
                  </Badge>
                </DataTable.Cell>
                <DataTable.Cell numeric>{usd(model.input_usd_per_million)}</DataTable.Cell>
                <DataTable.Cell numeric>{usd(model.output_usd_per_million)}</DataTable.Cell>
                <DataTable.Cell>
                  {model.listed_on === null ? (
                    <span className="text-fg-muted">{t('supervision.llm.notListed')}</span>
                  ) : (
                    format.day(model.listed_on)
                  )}
                </DataTable.Cell>
              </DataTable.Row>
            ))}
          </DataTable.Body>
        </DataTable.Root>
      )}
      <DataTable.Root caption={t('supervision.llm.promptsCaption')}>
        <DataTable.Head>
          <tr>
            <DataTable.HeaderCell>{t('supervision.llm.prompt')}</DataTable.HeaderCell>
            <DataTable.HeaderCell>{t('supervision.llm.purpose')}</DataTable.HeaderCell>
            <DataTable.HeaderCell>{t('supervision.llm.state')}</DataTable.HeaderCell>
          </tr>
        </DataTable.Head>
        <DataTable.Body>
          {inventory.prompts.map((use) => (
            <DataTable.Row key={use.prompt}>
              <th
                scope="row"
                className="px-4 py-3 text-left align-top font-mono text-caption font-normal text-fg"
              >
                {use.prompt}
              </th>
              <DataTable.Cell>{labels.purpose(use.purpose)}</DataTable.Cell>
              <DataTable.Cell>{onOff(use.active)}</DataTable.Cell>
            </DataTable.Row>
          ))}
        </DataTable.Body>
      </DataTable.Root>
    </Section>
  );
}
