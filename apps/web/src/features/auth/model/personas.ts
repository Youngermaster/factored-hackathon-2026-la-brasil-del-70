import type { Schema } from '@/shared/api';

/**
 * The demo personas seeded by `make seed` (docs/demo/personas.md). Ids are demo labels, not secrets; the
 * descriptions live in the locale files under `personas.<id>`. Shown only in demo mode.
 */
export interface Persona {
  readonly id: PersonaId;
  readonly role: Schema<'Role'>;
  readonly country?: Schema<'Country'>;
  readonly workflow?: Schema<'WorkflowId'>;
}

export type PersonaId =
  | 'acc-mx-accounts'
  | 'acc-co-payments'
  | 'acc-ar-similar-transfers'
  | 'crd-mx-two-cards'
  | 'crd-co-declined'
  | 'crd-ar-expired'
  | 'crd-mx-blocked'
  | 'dsp-co-unrecognized'
  | 'dsp-mx-open-case'
  | 'dsp-ar-repeat-complainer'
  | 'dsp-mx-similar-purchases'
  | 'cre-mx-complete'
  | 'cre-co-no-income'
  | 'cre-ar-borderline'
  | 'cre-mx-past-due'
  | 'cre-co-application'
  | 'agent-demo-01'
  | 'evaluator-demo-01';

const customer = (
  id: PersonaId,
  country: Schema<'Country'>,
  workflow: Schema<'WorkflowId'>,
): Persona => ({ id, role: 'customer', country, workflow });

export const PERSONAS: readonly Persona[] = [
  customer('acc-mx-accounts', 'MX', 'account_inquiry'),
  customer('acc-co-payments', 'CO', 'account_inquiry'),
  customer('acc-ar-similar-transfers', 'AR', 'account_inquiry'),
  customer('crd-mx-two-cards', 'MX', 'card_support'),
  customer('crd-co-declined', 'CO', 'card_support'),
  customer('crd-ar-expired', 'AR', 'card_support'),
  customer('crd-mx-blocked', 'MX', 'card_support'),
  customer('dsp-co-unrecognized', 'CO', 'dispute'),
  customer('dsp-mx-open-case', 'MX', 'dispute'),
  customer('dsp-ar-repeat-complainer', 'AR', 'dispute'),
  customer('dsp-mx-similar-purchases', 'MX', 'dispute'),
  customer('cre-mx-complete', 'MX', 'credit'),
  customer('cre-co-no-income', 'CO', 'credit'),
  customer('cre-ar-borderline', 'AR', 'credit'),
  customer('cre-mx-past-due', 'MX', 'credit'),
  customer('cre-co-application', 'CO', 'credit'),
  { id: 'agent-demo-01', role: 'agent' },
  { id: 'evaluator-demo-01', role: 'evaluator' },
];

/** Where each role lands after sign-in, and where a guard sends a role that opened another role's page. */
export function homeFor(role: Schema<'Role'>): string {
  return role === 'customer' ? '/' : '/console';
}
