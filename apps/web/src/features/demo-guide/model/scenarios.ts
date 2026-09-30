import type { PersonaId } from '@/features/auth';
import type { Schema } from '@/shared/api';

/**
 * The demo scenarios for judges and the pitch video: per workflow, the normal, ambiguous or unsupported, and
 * escalation paths, each in Spanish and Portuguese, played by a seeded persona (docs/demo/personas.md).
 *
 * The example messages are inputs the visitor types, shown verbatim in the language of the conversation they
 * demonstrate, so they live here as data rather than in the locale files (which translate the page around them).
 * Every message was driven through the real API with LLM_PROVIDER=fake on the seed of the committed sample (the
 * default `make seed` and the deployed demo) before it was listed; the backend scenario tests cover the same
 * phrasings. Every persona here is one that seed loads (data_platform/seed/personas.sample.yaml; a data_platform
 * test checks it). Words in brackets are placeholders the visitor fills from the previous answer.
 */
export type PathKind = 'normal' | 'ambiguous' | 'escalation';

/** A message to type, or a step on screen (a button, the code). */
export type Step =
  | { readonly say: string }
  | { readonly action: 'confirm_and_code' | 'review_button' | 'human_button' };

export type ScenarioId =
  | 'balances'
  | 'payment-details'
  | 'transfer-unsupported'
  | 'contested-balance'
  | 'card-block'
  | 'card-status'
  | 'card-unblock'
  | 'dispute-intake'
  | 'dispute-status'
  | 'dispute-details'
  | 'dispute-regulator'
  | 'credit-eligibility'
  | 'credit-status'
  | 'credit-missing-income'
  | 'credit-approval-request'
  | 'credit-review';

export interface Scenario {
  readonly id: ScenarioId;
  readonly workflow: Schema<'WorkflowId'>;
  readonly path: PathKind;
  readonly persona: PersonaId;
  readonly es: readonly Step[];
  readonly pt: readonly Step[];
}

const say = (text: string): Step => ({ say: text });

export const SCENARIOS: readonly Scenario[] = [
  {
    id: 'balances',
    workflow: 'account_inquiry',
    path: 'normal',
    persona: 'acc-mx-accounts',
    es: [say('¿Cuál es el saldo de mis cuentas?')],
    pt: [say('Qual é o saldo das minhas contas?')],
  },
  {
    id: 'payment-details',
    workflow: 'account_inquiry',
    path: 'ambiguous',
    persona: 'acc-mx-accounts',
    es: [say('¿Cuál es el estado de mi transferencia?')],
    pt: [say('Qual é a situação da minha transferência?')],
  },
  {
    id: 'transfer-unsupported',
    workflow: 'account_inquiry',
    path: 'ambiguous',
    persona: 'acc-mx-accounts',
    es: [say('Quiero hacer una transferencia a otra cuenta')],
    pt: [say('Quero fazer uma transferência para outra conta')],
  },
  {
    id: 'contested-balance',
    workflow: 'account_inquiry',
    path: 'escalation',
    persona: 'acc-mx-accounts',
    es: [say('Mi saldo está mal, quiero hablar con una persona')],
    pt: [say('O saldo da minha conta está errado')],
  },
  {
    id: 'card-block',
    workflow: 'card_support',
    path: 'normal',
    persona: 'crd-mx-two-cards',
    es: [
      say('Perdí mi tarjeta, bloquéala por favor'),
      say('la primera'),
      { action: 'confirm_and_code' },
    ],
    pt: [
      say('Perdi meu cartão, bloqueie por favor'),
      say('o primeiro'),
      { action: 'confirm_and_code' },
    ],
  },
  {
    id: 'card-status',
    workflow: 'card_support',
    path: 'ambiguous',
    persona: 'crd-co-declined',
    es: [say('¿Cuál es el estado de mis tarjetas?'), say('la primera')],
    pt: [
      say('Qual é a situação dos meus cartões?'),
      say('sobre os meus cartões'),
      say('o primeiro'),
    ],
  },
  {
    id: 'card-unblock',
    workflow: 'card_support',
    path: 'escalation',
    persona: 'crd-mx-blocked',
    es: [say('Quiero desbloquear mi tarjeta')],
    pt: [say('Quero desbloquear meu cartão')],
  },
  {
    id: 'dispute-intake',
    workflow: 'dispute',
    path: 'normal',
    persona: 'dsp-co-unrecognized',
    es: [
      say('Quiero el estado de cuenta de abril de mi tarjeta de crédito'),
      say('la primera'),
      say('No reconozco el cargo de [comercio] del [fecha] por [monto]'),
      say('Sí'),
      say('No, gracias'),
      { action: 'confirm_and_code' },
    ],
    pt: [
      say('Quero o extrato de abril do meu cartão de crédito'),
      say('o primeiro'),
      say('Não reconheço a cobrança de [estabelecimento] de [data] por [valor]'),
      say('Sim'),
      say('Não, obrigado'),
      { action: 'confirm_and_code' },
    ],
  },
  {
    id: 'dispute-status',
    workflow: 'dispute',
    path: 'normal',
    persona: 'dsp-mx-open-case',
    es: [say('¿Cómo va mi aclaración?')],
    pt: [say('Qual é a situação da minha contestação?')],
  },
  {
    id: 'dispute-details',
    workflow: 'dispute',
    path: 'ambiguous',
    persona: 'dsp-co-unrecognized',
    es: [say('No reconozco una compra con mi tarjeta')],
    pt: [say('Não reconheço uma compra no meu cartão')],
  },
  {
    id: 'dispute-regulator',
    workflow: 'dispute',
    path: 'escalation',
    persona: 'dsp-co-unrecognized',
    es: [
      say(
        'No reconozco un cargo en mi tarjeta y voy a presentar una queja ante la Superintendencia Financiera',
      ),
    ],
    pt: [
      say(
        'Não reconheço uma cobrança no meu cartão e vou registrar uma reclamação no Banco Central',
      ),
    ],
  },
  {
    id: 'credit-eligibility',
    workflow: 'credit',
    path: 'normal',
    persona: 'cre-mx-complete',
    es: [
      say('¿Qué préstamos personales tienen?'),
      say('¿Soy elegible para un préstamo personal de 50,000 pesos a 24 meses?'),
    ],
    pt: [
      say('Quais cartões de crédito vocês têm?'),
      say('Sou elegível para um empréstimo pessoal de 50 mil pesos em 24 meses?'),
    ],
  },
  {
    id: 'credit-status',
    workflow: 'credit',
    path: 'normal',
    persona: 'cre-co-application',
    es: [say('¿Cómo va mi solicitud de crédito?')],
    pt: [say('Como está a minha solicitação de crédito?')],
  },
  {
    id: 'credit-missing-income',
    workflow: 'credit',
    path: 'ambiguous',
    persona: 'cre-co-no-income',
    es: [say('¿Soy elegible para un préstamo personal de 5 millones de pesos a 24 meses?')],
    pt: [say('Sou elegível para um empréstimo pessoal de 5 milhões de pesos em 24 meses?')],
  },
  {
    id: 'credit-approval-request',
    workflow: 'credit',
    path: 'ambiguous',
    persona: 'cre-mx-complete',
    es: [say('Apruébame el crédito ya')],
    pt: [say('Quero que aprovem meu empréstimo agora')],
  },
  {
    id: 'credit-review',
    workflow: 'credit',
    path: 'escalation',
    persona: 'cre-ar-borderline',
    es: [
      say('¿Soy elegible para un préstamo personal de 500 mil pesos a 12 meses?'),
      { action: 'review_button' },
    ],
    pt: [
      say('Sou elegível para um empréstimo pessoal de 500 mil pesos em 12 meses?'),
      { action: 'review_button' },
    ],
  },
];

export const WORKFLOW_ORDER: readonly Schema<'WorkflowId'>[] = [
  'account_inquiry',
  'card_support',
  'dispute',
  'credit',
];
