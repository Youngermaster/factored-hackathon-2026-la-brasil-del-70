import { useTranslation } from 'react-i18next';

import type { Schema } from '@/shared/api';

type Heading = 'synthetic_notice' | 'reasons' | 'missing';

/**
 * The eligibility sentences, from the locale files' `eligibility` tree, which mirrors the policy pack's
 * `policies/messages/eligibility.<language>.yaml` word for word (tooling/eligibility-copy.test.ts). A code the
 * pack adds before the web copy is shown as the code, never dropped.
 */
export function useEligibilityCopy() {
  const { t, i18n } = useTranslation();
  const lookup = (key: string, fallback: string) =>
    i18n.exists(key) ? String(t(key as never)) : fallback;
  return {
    heading: (name: Heading) => t(`eligibility.heading.${name}`),
    outcome: (outcome: Schema<'EligibilityOutcome'>) => t(`eligibility.outcome.${outcome}`),
    uncertainty: (value: Schema<'UncertaintyStatement'>) => t(`eligibility.uncertainty.${value}`),
    reviewPath: (value: Schema<'ReviewPath'>) => t(`eligibility.review_path.${value}`),
    reason: (code: string) => lookup(`eligibility.reason.${code}`, code),
    missingFact: (fact: string) => lookup(`eligibility.missing_fact.${fact}`, fact),
  };
}
