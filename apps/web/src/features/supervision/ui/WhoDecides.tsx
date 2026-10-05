import { useTranslation } from 'react-i18next';

import { cx } from '@/shared/lib/cx';

import type { ModelInventory } from '../api/supervision';
import { useSupervisionLabels } from './labels';
import { Section } from './Section';

type Tone = 'understanding' | 'decision' | 'risk';

const TONES: Record<Tone, string> = {
  understanding: 'border-t-understanding',
  decision: 'border-t-decision',
  risk: 'border-t-risk',
};

const STEPS = [
  { key: 'propose', tone: 'understanding' },
  { key: 'decide', tone: 'decision' },
  { key: 'act', tone: 'decision' },
  { key: 'escalate', tone: 'risk' },
] as const;

/**
 * Where AI stops and rules decide: the four steps every request passes, each with the versions this process serves.
 * Blue is model understanding, yellow deterministic decisions and verified actions, red the hand-over to people.
 */
export function WhoDecides({ inventory }: { readonly inventory: ModelInventory }) {
  const { t } = useTranslation();
  const labels = useSupervisionLabels();
  const primary = inventory.llm.models.find((model) => model.role === 'primary');
  const learnedParts = inventory.components.filter((item) =>
    ['router', 'resolver', 'risk_estimator'].includes(item.component),
  );
  const details: Record<(typeof STEPS)[number]['key'], readonly string[]> = {
    propose: [
      primary === undefined
        ? t('supervision.decides.noModel')
        : t('supervision.decides.llmLine', { model: primary.model_id }),
      ...learnedParts.map((item) =>
        t('supervision.decides.componentLine', {
          component: labels.component(item.component),
          model: item.served ?? t('supervision.models.kinds.unavailable'),
        }),
      ),
    ],
    decide: [t('supervision.decides.packLine', { version: inventory.policy_pack_version })],
    act: [
      t('supervision.decides.workflowsLine', {
        workflows: inventory.workflows_enabled
          .map((workflow) => t(`glass.workflows.${workflow}`))
          .join(', '),
      }),
    ],
    escalate: [t('supervision.decides.handoffLine')],
  };
  return (
    <Section
      id="supervision-decides"
      title={t('supervision.decides.title')}
      intro={t('supervision.decides.intro')}
    >
      <ol className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {STEPS.map((step, index) => (
          <li
            key={step.key}
            className={cx(
              'flex flex-col gap-2 rounded-card border border-border border-t-4 bg-surface p-4',
              TONES[step.tone],
            )}
          >
            <span className="font-mono text-caption text-fg-muted">{index + 1}</span>
            <h3 className="text-body font-semibold text-fg">
              {t(`supervision.decides.steps.${step.key}.title`)}
            </h3>
            <p className="text-small text-fg-secondary">
              {t(`supervision.decides.steps.${step.key}.body`)}
            </p>
            <ul className="mt-auto flex flex-col gap-1 border-t border-border pt-2">
              {details[step.key].map((line) => (
                <li key={line} className="font-mono text-caption break-words text-fg">
                  {line}
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ol>
    </Section>
  );
}
