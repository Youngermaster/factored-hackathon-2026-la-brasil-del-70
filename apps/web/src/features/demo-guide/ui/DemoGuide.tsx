import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { Badge, Card, ForwardIcon } from '@/shared/ui';

import type { PersonaId } from '@/features/auth';

import { SCENARIOS, WORKFLOW_ORDER, type Scenario, type Step } from '../model/scenarios';
import { CopyMessage } from './CopyMessage';

// Persona ids are demo labels (identifiers), not copy.
const AGENT: PersonaId = 'agent-demo-01';
const EVALUATOR: PersonaId = 'evaluator-demo-01';

/**
 * The demo guide for judges and the pitch video: how to sign in as a seeded persona, then per workflow the normal,
 * ambiguous or unsupported, and escalation paths, each in Spanish and Portuguese, with copyable messages.
 */
export function DemoGuide() {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-12">
      <div className="flex max-w-3xl flex-col gap-3">
        <h1 className="font-display text-display font-semibold tracking-tight text-fg">
          {t('demo.title')}
        </h1>
        <p className="text-lead text-fg-secondary">{t('demo.intro')}</p>
      </div>
      <Start />
      {WORKFLOW_ORDER.map((workflow) => (
        <section
          key={workflow}
          aria-labelledby={`demo-${workflow}`}
          className="flex flex-col gap-4"
        >
          <div className="flex flex-col gap-1">
            <h2 id={`demo-${workflow}`} className="text-heading font-semibold text-fg">
              {t(`glass.workflows.${workflow}`)}
            </h2>
            <p className="max-w-prose text-small text-fg-secondary">
              {t(`home.topics.${workflow}Body`)}
            </p>
          </div>
          <ul className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            {SCENARIOS.filter((scenario) => scenario.workflow === workflow).map((scenario) => (
              <li key={scenario.id}>
                <ScenarioCard scenario={scenario} />
              </li>
            ))}
          </ul>
        </section>
      ))}
      <Console />
    </div>
  );
}

function Start() {
  const { t } = useTranslation();
  const steps = ['step1', 'step2', 'step3', 'step4', 'step5'] as const;
  return (
    <section aria-labelledby="demo-start" className="flex max-w-3xl flex-col gap-3">
      <h2 id="demo-start" className="text-title font-semibold text-fg">
        {t('demo.start.title')}
      </h2>
      <ol className="flex list-decimal flex-col gap-2 pl-5 text-body text-fg">
        {steps.map((step) => (
          <li key={step}>{t(`demo.start.${step}`)}</li>
        ))}
      </ol>
      <p>
        <Link
          to="/login"
          className="inline-flex items-center gap-1.5 font-semibold text-fg underline underline-offset-4"
        >
          {t('demo.signIn')}
          <ForwardIcon aria-hidden="true" size={16} />
        </Link>
      </p>
    </section>
  );
}

function ScenarioCard({ scenario }: { readonly scenario: Scenario }) {
  const { t } = useTranslation();
  const titleId = `scenario-${scenario.id}`;
  return (
    <Card.Root aria-labelledby={titleId} className="h-full">
      <Card.Header
        title={<span id={titleId}>{t(`demo.scenarios.${scenario.id}.title`)}</span>}
        description={t(`demo.scenarios.${scenario.id}.note`)}
        action={
          <Badge tone={scenario.path === 'escalation' ? 'risk' : 'neutral'}>
            {t(`demo.paths.${scenario.path}`)}
          </Badge>
        }
      />
      <Card.Body className="flex flex-col gap-4">
        <p className="text-small text-fg-secondary">
          {t('demo.persona')} <span className="font-mono text-fg">{scenario.persona}</span>
          {': '}
          {t(`personas.${scenario.persona}`)}
        </p>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          <Steps label={t('demo.spanish')} steps={scenario.es} />
          <Steps label={t('demo.portuguese')} steps={scenario.pt} />
        </div>
      </Card.Body>
    </Card.Root>
  );
}

function Steps({ label, steps }: { readonly label: string; readonly steps: readonly Step[] }) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-2">
      <p className="text-small font-semibold text-fg">{label}</p>
      <ol className="flex flex-col gap-2">
        {steps.map((step, index) => (
          <li key={`${String(index)}-${'say' in step ? step.say : step.action}`}>
            {'say' in step ? (
              <CopyMessage text={step.say} />
            ) : (
              <p className="px-1 text-small text-fg-secondary">
                {t(`demo.actions.${step.action}`)}
              </p>
            )}
          </li>
        ))}
      </ol>
    </div>
  );
}

function Console() {
  const { t } = useTranslation();
  return (
    <section aria-labelledby="demo-console" className="flex max-w-3xl flex-col gap-3">
      <h2 id="demo-console" className="text-heading font-semibold text-fg">
        {t('demo.console.title')}
      </h2>
      <ul className="flex flex-col gap-3 text-body text-fg">
        <li>
          <span className="font-mono">{AGENT}</span>: {t('demo.console.agent')}
        </li>
        <li>
          <span className="font-mono">{EVALUATOR}</span>: {t('demo.console.evaluator')}
        </li>
      </ul>
      <p className="text-small text-fg-secondary">{t('demo.reset')}</p>
    </section>
  );
}
